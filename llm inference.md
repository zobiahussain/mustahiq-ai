#step-1
install tailscael and accept my invitation

#step-2
tailscale ip


#step-3
curl.exe http://100.72.1.8:11434/api/tags

and you should see something like models, qwen3:4b


#step-4 to us it in codeimport requests
OLLAMA_URL = "http://100.72.1.8:11434"

response = requests.post(
    f"{OLLAMA_URL}/api/chat",
    json={
        "model": "qwen3:4b",
        "messages": [
            {
                "role": "user",
                "content": "Hello Qwen!"
            }
        ],
        "stream": False
    }
)

print(response.json())

