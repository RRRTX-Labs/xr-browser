# SAST canary fixture — py-no-pickle. Never run/shipped as tooling.
import pickle


def trigger(blob: bytes):
    return pickle.loads(blob)   # banned: untrusted deserialization
