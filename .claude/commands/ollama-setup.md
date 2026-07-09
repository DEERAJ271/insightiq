Verify local Ollama is ready for offline LLM testing:
1. Check if Ollama is running: curl http://localhost:11434/api/tags
2. List available models and confirm at least one is pulled
3. If llama3.2 or similar isn't available, report the exact `ollama pull`
   command needed
4. Do a trivial test call (a single "say OK" prompt) to confirm the
   API responds correctly, and report the response time

This is a pure infrastructure check — don't touch any project files.
