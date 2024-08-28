import openai
import anthropic
import requests
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()

class AiType:
    GPT = 'gpt'
    ANTHROPIC = 'anthropic'
    CLOVARX = 'clovar'

class Gpt:
    def __init__(self):
        pass

    def __set_api_key(self) -> openai.OpenAI:
        api_key = [os.environ.get('OpenaiAPI')]
        random_integer = 0  # random.randint(0, len(api_key) - 1)
        return openai.OpenAI(api_key=api_key[random_integer])

    def request(self, messages):
        client = self.__set_api_key()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=4096,
            temperature=0.2,
        )
        return response.choices[0].message.content

class Anthropic3:
    def __init__(self):
        self.client = anthropic.Client(api_key=os.environ.get('Anthropic3API'))

    def request(self, msg=None):
        common_params = {
            "model": "claude-3-opus-20240229",
            "max_tokens": 4096,
            "temperature": 0.2,
            "messages": msg
        }
        response = self.client.messages.create(**common_params)
        return response.content[0].text

class ClovarX:
    host = os.environ.get('CloverHost')
    api_key = os.environ.get('CloverAPI')
    api_key_primary_val = os.environ.get('CloverAPIPrimary')
    request_id = os.environ.get('CloverRequestId')

    def __init__(self):
        self._host = self.host
        self._api_key = self.api_key
        self._api_key_primary_val = self.api_key_primary_val
        self._request_id = self.request_id

    def execute(self, completion_request):
        headers = {
            'X-NCP-CLOVASTUDIO-API-KEY': self._api_key,
            'X-NCP-APIGW-API-KEY': self._api_key_primary_val,
            'X-NCP-CLOVASTUDIO-REQUEST-ID': self._request_id,
            'Content-Type': 'application/json; charset=utf-8',
            'Accept': 'text/event-stream'
        }
        with requests.post(self._host + '/testapp/v1/chat-completions/HCX-003',
                           headers=headers, json=completion_request, stream=True) as r:
            lines = list(r.iter_lines())
            answer = json.loads(lines[-6].decode("utf-8")[5:])
            return answer["message"]["content"]

    def request(self, messages, topP=0.47, topK=0, maxTokens=762, temperature=0.16, repeatPenalty=0.16, stopBefore=[], includeAiFilters=False, seed=0):
        request_data = {
            'messages': messages,
            'topP': topP,
            'topK': topK,
            'maxTokens': maxTokens,
            'temperature': temperature,
            'repeatPenalty': repeatPenalty,
            'stopBefore': stopBefore,
            'includeAiFilters': includeAiFilters,
            'seed': seed
        }
        return self.execute(request_data)

gpt = Gpt()
anthropic3 = Anthropic3()
clovar_x = ClovarX()

def gpt_request(prompt, ai_type=AiType.GPT):
    messages = [{"role": "user", "content": prompt}]
    if ai_type == AiType.GPT:
        return gpt.request(messages)
    elif ai_type == AiType.ANTHROPIC:
        return anthropic3.request(messages)
    elif ai_type == AiType.CLOVARX:
        return clovar_x.request(messages)

# Helper function to handle rate limit errors and retry
def gpt_request_with_retry(prompt, ai_type=AiType.GPT, max_retries=5):
    for attempt in range(max_retries):
        try:
            return gpt_request(prompt, ai_type)
        except openai.RateLimitError as e:
            retry_after = e.response.headers.get("Retry-After", 20)  # Default to 20 seconds
            print(f"Rate limit exceeded. Retrying in {retry_after} seconds...")
            time.sleep(float(retry_after))
    raise Exception("Rate limit exceeded after retries")
