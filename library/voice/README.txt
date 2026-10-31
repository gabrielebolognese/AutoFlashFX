Files that go here (audio is never tracked by git):
- reference.wav: 10 to 30 seconds of your clean speech at reel energy, for the voice engines that clone a voice.
- memo.wav (or memo.m4a, memo.mp3): a 5 to 10 minute voice memo; M5 transcribes it to build library/profile/voice.md.
Until reference.wav exists the pipeline uses the kokoro stock voice.
