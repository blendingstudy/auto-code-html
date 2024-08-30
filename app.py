from flask import Flask, render_template, request, jsonify, send_from_directory
from config import Config
from ai_models import gpt_request_with_retry
import os
import json
import re
import threading

app = Flask(__name__)
app.config.from_object(Config)

# Global variables for account and project GUIDs
account_guid = ''
project_guid = ''


def validate_flowchart(project_description, flowchart):
    if not project_description.strip():
        return False, "Project description cannot be empty."
    if not flowchart.strip():
        return False, "Flowchart cannot be empty."
    return True, ""


def construct_prompt(project_description, flowchart, is_new_project, has_been_requested_before):
    if is_new_project or not has_been_requested_before:
        initial_prompt = project_description + "\n\n\n" + flowchart
    else:
        initial_prompt = flowchart
    prompt = initial_prompt + """
    \n\n\n
    위의 내용을 토대로 각 기능별로 필요한 함수들을 나누고, 각 함수의 파라미터까지 자세히 포함한 함수 호출표를 만들어줘.
    각 기능별로 함수가 나뉘어지고 각 함수의 파라미터까지 명확히 기술된 형태로 작성해줘.
    답변은 json으로만 해줘. 파싱하기 위함이라 다른걸로 하면 안돼.
    예시:
    {
        "1": {
            "title": "사용자 인증 및 회원 관리",
            "functions": [
                {
                    "name": "auth_controller.register",
                    "description": "회원가입 처리",
                    "parameters": ["username", "email", "password"]
                },
                {
                    "name": "auth_controller.login",
                    "description": "로그인 처리",
                    "parameters": ["email", "password"]
                }
                // 다른 함수들...
            ]
        },
        "2": {
            "title": "상품 관리",
            "functions": [
                {
                    "name": "product_controller.create_product",
                    "description": "새로운 상품 생성",
                    "parameters": ["name", "description", "price", "quantity"]
                }
                // 다른 함수들...
            ]
        }
        // 다른 기능들...
    }
    """
    return prompt


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/generate_code', methods=['POST'])
def generate_code():
    global account_guid, project_guid

    data = request.get_json()
    account_guid = data['account_guid']
    project_guid = data['project_guid']
    project_description = data['project_description']
    flowchart = data['flowchart']

    is_valid, error_message = validate_flowchart(project_description, flowchart)
    if not is_valid:
        return jsonify({'error': error_message}), 400

    path = f'code/{account_guid}/{project_guid}/project_data.json'
    if os.path.exists(path):
        with open(path, 'r', encoding='cp949') as f:
            project_data = json.load(f)
            existing_description = project_data['project_description']
            is_new_project = False
            has_been_requested_before = 'gpt_request' in project_data
    else:
        existing_description = ""
        is_new_project = True
        has_been_requested_before = False

    if existing_description != project_description:
        is_new_project = True

    constructed_prompt = construct_prompt(
        project_description,
        flowchart,
        is_new_project,
        has_been_requested_before
    )

    response = gpt_request_with_retry(constructed_prompt)
    project_data = {
        'account_guid': account_guid,
        'project_guid': project_guid,
        'project_description': project_description,
        'flowchart': flowchart,
        'gpt_request': response
    }
    save_project_data(project_data)
    formatted_response = format_response(response)
    save_function_call_chart(formatted_response)

    return jsonify({'formatted_response': formatted_response})


@app.route('/modify_function_call_chart', methods=['POST'])
def modify_function_call_chart():
    global account_guid, project_guid

    data = request.get_json()
    account_guid = data['account_guid']
    project_guid = data['project_guid']
    modification_prompt = data['modification_prompt']

    path = f'code/{account_guid}/{project_guid}/project_data.json'
    if not os.path.exists(path):
        return jsonify({'error': 'Project not found'}), 404

    with open(path, 'r', encoding='cp949') as f:
        project_data = json.load(f)

    existing_chart = project_data.get('gpt_request', "")
    constructed_prompt = existing_chart + "\n\n" + modification_prompt
    constructed_prompt += "답변은 json으로만 해줘. 파싱하기 위함이라 다른걸로 하면 안돼."

    response = gpt_request_with_retry(constructed_prompt)
    try:
        formatted_response = format_response(response)
    except json.JSONDecodeError as e:
        return jsonify({'error': '응답을 JSON으로 파싱하는데 실패했습니다.', 'details': str(e)}), 500

    save_function_call_chart(formatted_response)

    return jsonify({'formatted_response': formatted_response})


@app.route('/generate_project_code', methods=['POST'])
def generate_project_code():
    global account_guid, project_guid

    data = request.get_json()
    account_guid = data['account_guid']
    project_guid = data['project_guid']

    path = f'code/{account_guid}/{project_guid}/project_data.json'
    function_call_path = f'code/{account_guid}/{project_guid}/function_call_chart.txt'
    if not os.path.exists(path):
        return jsonify({'error': 'Project not found'}), 404
    if not os.path.exists(function_call_path):
        return jsonify({'error': 'function call chart not found'}), 404

    with open(path, 'r', encoding='cp949') as f:
        project_data = json.load(f)
        project_description = project_data['project_description']
        flowchart = project_data['flowchart']

    with open(function_call_path, 'r', encoding='cp949') as f:
        function_call_chart_content = f.read()

    prompt = f"{project_description}\n\n{flowchart}\n\n{function_call_chart_content}\n\n"
    prompt += """
    Based on the provided project description, flowchart, and function call chart, create a detailed project structure. 
    The project should be a only one HTML file and every code must in HTML file. 
    Include a design plan summary and a list of code files with their paths, object names, and function lists. 
    Do not include the implementation of the code, only the structure. 
    Provide the response in JSON format for easy parsing.
    If it is a code file, it must include functionList:[]
    If it's a resource file, you don't need a functionList.
    If it's an object file, you should also have objectName.
    If it's not an object, you can give the field value of NoneObject.
    Example:
    {
        "plan": "Design summary...",
        "Files": [
            {"path": "app", "fname": "app.py", "objectName": None, "functionList": ["create_app()"]},
            {"path": "app/controllers", "fname": "auth_controller.py", "objectName": None, "functionList": ["register()", "login()"]},
            {"path": "app/templates", "fname": "index.html"},
            // More files...
        ]
    }
    """

    response = gpt_request_with_retry(prompt)
    code_structure = parse_code_structure(response)
    save_code_structure(code_structure)

    files = code_structure.get('Files', [])
    threads = []

    for file_info in files:
        t = threading.Thread(target=implement_file, args=(file_info, code_structure))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # HTML 파일 경로 가져오기
    html_file = next((file for file in files if file['fname'].endswith('.html')), None)
    if html_file:
        html_file_path = f'/{account_guid}/{project_guid}/{html_file["path"]}/{html_file["fname"]}'
    else:
        html_file_path = None

    return jsonify({'code_structure': code_structure, 'html_file_path': html_file_path})


@app.route('/load_project', methods=['POST'])
def load_project():
    global account_guid, project_guid

    data = request.get_json()
    account_guid = data['account_guid']
    project_guid = data['project_guid']

    path = f'code/{account_guid}/{project_guid}/project_data.json'
    if os.path.exists(path):
        with open(path, 'r', encoding='cp949') as f:
            project_data = json.load(f)
        function_call_chart = load_function_call_chart()
        files = load_file_list(account_guid, project_guid)

        html_file_path = None
        for file in files:
            if file['fname'].endswith('.html'):
                html_file_path = f'/{account_guid}/{project_guid}/{file["path"]}/{file["fname"]}'
                break

        return jsonify(
            {"exists": True, "project_data": project_data, "function_call_chart": function_call_chart, "files": files,
             "html_file_path": html_file_path})
    else:
        return jsonify({"exists": False})


@app.route('/get_file_code', methods=['POST'])
def get_file_code():
    global account_guid, project_guid

    file_info = request.get_json()
    path = file_info.get('path', '')
    fname = file_info.get('fname', '')

    # 파일 경로 생성
    file_path = f'code/{account_guid}/{project_guid}/{path}/{fname}'
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='cp949') as file:
            code = file.read()
        return jsonify({"code": code})
    else:
        return jsonify({"code": "파일을 찾을 수 없습니다."}), 404


@app.route('/save_file_code', methods=['POST'])
def save_file_code():
    global account_guid, project_guid

    data = request.get_json()
    path = data.get('path', '')
    fname = data.get('fname', '')
    code = data.get('code', '')

    # 파일 경로 생성
    file_path = f'code/{account_guid}/{project_guid}/{path}/{fname}'
    with open(file_path, 'w', encoding='cp949') as file:
        file.write(code)
    return jsonify({"status": "success"})


@app.route('/modify_code', methods=['POST'])
def modify_code():
    global account_guid, project_guid

    data = request.get_json()
    file_info = data['file_info']
    modification_prompt = data['modification_prompt']
    current_code = data['current_code']

    prompt = f"Modify the following code:\n\n{current_code}\n\nModification request:\n{modification_prompt}"

    response = gpt_request_with_retry(prompt)

    modified_code = extract_code_from_response(response)

    # 수정된 코드를 파일에 저장
    save_file(file_info['path'], file_info['fname'], modified_code)

    return jsonify({"modified_code": modified_code})


@app.route('/run_project', methods=['POST'])
def run_project():
    global account_guid, project_guid

    data = request.get_json()
    account_guid = data['account_guid']
    project_guid = data['project_guid']

    path = f'code/{account_guid}/{project_guid}/project_data.json'

    if not os.path.exists(path):
        return jsonify({'error': 'Project not found'}), 404

    with open(path, 'r', encoding='cp949') as f:
        project_data = json.load(f)

    # HTML 파일 경로 가져오기
    html_file_path = next((f'code/{account_guid}/{project_guid}/{file["path"]}/{file["fname"]}'
                           for file in load_file_list(account_guid, project_guid)
                           if file['fname'].endswith('.html')), None)

    if html_file_path and os.path.exists(html_file_path):
        with open(html_file_path, 'r', encoding='cp949') as f:
            html_content = f.read()
        return jsonify({'html_content': html_content})  # HTML 내용을 직접 반환
    else:
        return jsonify({'error': 'HTML file not found'}), 404


@app.route('/code/<account_guid>/<project_guid>/<path:file_path>', methods=['GET'])
def serve_html(account_guid, project_guid, file_path):
    file_dir = f'code/{account_guid}/{project_guid}'
    return send_from_directory(file_dir, file_path)


def extract_code_from_response(response):
    code_match = re.search(r'```(?:.|\n)*?\n(.*?)```', response, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()
    return response.strip()


def load_file_list(account_guid, project_guid):
    path = f'code/{account_guid}/{project_guid}'
    excluded_files = {'function_call_chart.txt', 'code_structure.json', 'project_data.json'}
    file_list = []
    for root, dirs, files in os.walk(path):
        for file in files:
            if file not in excluded_files:
                file_info = {
                    'path': os.path.relpath(root, path),
                    'fname': file
                }
                file_list.append(file_info)
    return file_list


def parse_code_structure(response):
    response = response.strip()
    print(f"Response: {response}")  # 응답 출력하여 디버깅
    if response.startswith('{'):
        try:
            code_structure = json.loads(response)
            return code_structure
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return {}
    else:
        json_match = re.search(r'```json(.*?)```', response, re.DOTALL)
        if json_match:
            json_content = json_match.group(1).strip()
            print(f"Extracted JSON content: {json_content}")  # 추출된 JSON 내용 출력하여 디버깅
            try:
                code_structure = json.loads(json_content)
                return code_structure
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                return {}
    return {}


def save_code_structure(code_structure):
    global account_guid, project_guid

    path = f'code/{account_guid}/{project_guid}'
    os.makedirs(path, exist_ok=True)
    with open(f'{path}/code_structure.json', 'w', encoding='cp949') as f:
        json.dump(code_structure, f)


def implement_file(file_info, full_code_structure):
    global account_guid, project_guid

    path = file_info.get('path', '')
    fname = file_info.get('fname', '')
    object_name = file_info.get('objectName', '')
    function_list = file_info.get('functionList', [])

    # GPT에 전달할 프롬프트 생성
    prompt = f"Based on the following code structure, implement the functions for the file {fname}:\n\n"
    prompt += json.dumps(full_code_structure, indent=2)
    prompt += f"\n\nImplement the following functions for {object_name}:\n"
    if function_list:
        for function in function_list:
            prompt += f"- {function}\n"
    else:
        prompt += "No specific functions provided."

    # GPT 요청을 통해 코드를 생성
    response = gpt_request_with_retry(prompt)

    # 응답에서 코드 부분 추출
    code_match = re.search(r'```(?:.|\n)*?\n(.*?)```', response, re.DOTALL)
    if code_match:
        file_content = code_match.group(1).strip()
    else:
        file_content = response

    # 파일 저장
    save_file(path, fname, file_content)


def save_file(path, fname, content):
    global account_guid, project_guid

    full_path = f'code/{account_guid}/{project_guid}/{path}'
    os.makedirs(full_path, exist_ok=True)
    with open(f'{full_path}/{fname}', 'w', encoding='cp949') as f:
        f.write(content)


def format_response(response):
    formatted_response = ""
    try:
        if response.strip().startswith("```json"):
            response = response.strip()[7:-3].strip()
        if not response:
            return 'Empty JSON response'
        print(response)
        response_json = json.loads(response)
        for key, value in response_json.items():
            formatted_response += f"{key}. {value['title']}\n"
            for func in value['functions']:
                formatted_response += f"    - {func['name']}({', '.join(func['parameters'])}): {func['description']}\n"
    except Exception as e:
        return f'Error: {str(e)}'
    return formatted_response


def save_function_call_chart(chart):
    global account_guid, project_guid

    path = f'code/{account_guid}/{project_guid}'
    os.makedirs(path, exist_ok=True)
    with open(f'{path}/function_call_chart.txt', 'w', encoding='cp949') as f:
        f.write(chart)


def load_function_call_chart():
    global account_guid, project_guid

    path = f'code/{account_guid}/{project_guid}/function_call_chart.txt'
    if os.path.exists(path):
        with open(path, 'r', encoding='cp949') as f:
            return f.read()
    return ""


def save_project_data(project_data):
    global account_guid, project_guid

    path = f'code/{account_guid}/{project_guid}'
    os.makedirs(path, exist_ok=True)
    with open(f'{path}/project_data.json', 'w', encoding='cp949') as f:
        json.dump(project_data, f)


if __name__ == '__main__':
    app.run(debug=True)
