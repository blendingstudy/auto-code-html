from ai_models import gpt_request, AiType

def generate_code(flowchart):
    prompt = f"Generate code for the following flowchart: {flowchart}"
    response = gpt_request(prompt, ai_type=AiType.GPT)
    functions = response.split("\n")  # 적절한 파싱 로직 필요
    call_order = []  # 적절한 호출 순서 추출 로직
    return functions, call_order
