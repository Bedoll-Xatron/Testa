import sys
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    transcript = YouTubeTranscriptApi.get_transcript("y_jmFVoXu5I", languages=['ko'])
    full_text = " ".join([t['text'] for t in transcript])
    print(full_text[:3000]) # 처음 3000자만 출력
except ImportError:
    print("youtube_transcript_api not installed.")
except Exception as e:
    print(f"Error: {e}")
