import os
from dotenv import load_dotenv, find_dotenv

print("Python is running")
print(".env file found at:", find_dotenv() or "NONE")
load_dotenv()

for name in ("NEBIUS_API_KEY", "TAVILY_API_KEY"):
    k = os.environ.get(name, "")
    has_bad_char = any(c in k for c in " \"'\n\r\t")
    print(f"{name}: length={len(k)}, first4={k[:4]}, has space/quote={has_bad_char}")

print("Testing Nebius key...")
try:
    from openai import OpenAI
    client = OpenAI(
        base_url="https://api.tokenfactory.nebius.com/v1/",
        api_key=os.environ["NEBIUS_API_KEY"],
    )
    res = client.chat.completions.create(
    model="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    messages=[{"role": "user", "content": "ping"}],
    max_tokens=5
)
    print("Nebius key WORKS. Inference response:", res.choices[0].message.content)
except Exception as e:
    print("Nebius key FAILED:", str(e)[:200])