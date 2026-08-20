import os

from openai import OpenAI


base_url = os.environ["VERDA_ENDPOINT"].rstrip("/")
api_key = os.environ["VERDA_INFERENCE_KEY"]

client = OpenAI(base_url=f"{base_url}/v1", api_key=api_key, timeout=900.0)

response = client.chat.completions.create(
    model="qwen3.8-27b",
    messages=[
        {"role": "system", "content": "You are a cybersecurity analyst."},
        {
            "role": "user",
            "content": (
                "A Windows host suddenly starts making repeated LDAP queries "
                "followed by abnormal Kerberos service ticket requests. "
                "Explain what you would investigate."
            ),
        },
    ],
    temperature=0.7,
    top_p=0.8,
    max_tokens=1000,
)

print(response.choices[0].message.content)
