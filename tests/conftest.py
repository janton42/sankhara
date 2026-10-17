import os

# Keep Kivy from parsing pytest's CLI args and flooding the output with logs.
os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")
