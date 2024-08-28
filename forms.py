from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length

class FlowchartForm(FlaskForm):
    project_description = TextAreaField(
        'Project Description',
        default='프론트엔드인 html로만 이루어진 가위바위보 게임을 만들건데. 사용자가 가위, 바위, 보 중에 하나를 선택하면 컴퓨터가 랜덤으로 하나를 골라서 승패를 결정하게 해줘.',
        validators=[DataRequired(), Length(min=10, message="Project description must be at least 10 characters long.")]
    )
    flowchart = TextAreaField(
        'Flowchart',
        default='1. 사용자가 [가위, 바위, 보] 중에 하나 선택\n2. 컴퓨터가 [가위, 바위, 보] 중에 랜덤으로 하나 선택\n3. 승패를 화면에 출력\n4. 다시하기 버튼을 누르면 다시 1번부터 진행',
        validators=[DataRequired(), Length(min=20, message="Flowchart must be at least 20 characters long.")]
    )
    submit = SubmitField('Submit')
