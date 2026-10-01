# Builds a clean demo clip: Windows offline TTS (en-IN voice) reads a Hinglish script over silent footage.
# Usage: powershell -File samples/make_tts_sample.ps1 -Footage <video> -Script samples/demo_script.txt -Out samples/demo_input.mp4
param([string]$Footage, [string]$Script, [string]$Out, [string]$Voice = "Heera")

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime]

function Await($op, [Type]$type) {
    $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' }
    $task = $asTask.MakeGenericMethod($type).Invoke($null, @($op))
    $task.Wait() | Out-Null
    $task.Result
}

$tts = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$tts.Voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.DisplayName -match $Voice } | Select-Object -First 1
$stream = Await ($tts.SynthesizeTextToStreamAsync((Get-Content $Script -Raw))) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
$reader = New-Object Windows.Storage.Streams.DataReader($stream.GetInputStreamAt(0))
$size = [uint32]$stream.Size
$null = Await ($reader.LoadAsync($size)) ([uint32])
$bytes = New-Object byte[] $size
$reader.ReadBytes($bytes)
$wav = [IO.Path]::ChangeExtension($Out, ".voice.wav")
[IO.File]::WriteAllBytes($wav, $bytes)

ffmpeg -y -v error -stream_loop -1 -i $Footage -i $wav -map 0:v -map 1:a -shortest -c:v libx264 -crf 20 -pix_fmt yuv420p -c:a aac -b:a 160k $Out
Remove-Item $wav
Write-Output "Wrote $Out"
