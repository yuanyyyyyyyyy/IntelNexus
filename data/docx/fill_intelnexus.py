"""
根据IntelNexus项目填写江西省高等学校大学生创新创业训练计划项目申报表
基于模板：附件1+江西省高等学校大学生创新创业训练计划项目申报表－20260305.docx
"""

from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import datetime

def fill_intelnexus_application():
    # 读取空白模板
    doc = Document('附件1+江西省高等学校大学生创新创业训练计划项目申报表－20260305.docx')

    # IntelNexus项目信息
    project_name = "IntelNexus：AI驱动的多源网络情报分析平台"
    primary_discipline = "计算机科学与技术"
    secondary_discipline = "人工智能"
    key_area = "人工智能"
    project_source = "A"  # 学生自主选题

    # 项目简介（限200字）
    project_intro = """IntelNexus是一个AI驱动的多源网络情报分析平台，能够从网页、学术论文、新闻资讯和暗网等多个来源自动搜索和分析信息，并利用大语言模型生成专业情报报告。项目支持多引擎聚合搜索、智能内容抓取、LLM深度分析和多格式报告导出，应用于市场调研、舆情监测、学术研究等场景。"""

    # 团队成员信息
    team_members = {
        'leader': {'name': '胡瑾', 'student_id': '20230203093', 'grade': '23级'},
        'members': [
            {'name': '游钰翔', 'student_id': '20230201130', 'grade': '23级'},
            {'name': '喻庆程', 'student_id': '', 'grade': '23级'},
            {'name': '高江南', 'student_id': '', 'grade': '23级'},
        ]
    }

    # 指导教师信息
    first_teacher = {'name': '李涛', 'age': '46', 'achievements': '2024年，华为ICT大赛2023-2024江西省实践赛，云赛道本科组，获优秀指导教师（省级）。2024年，华为ICT大赛2023-2024江西省实践赛，云赛道本科组，一等奖1项（省级）。'}

    # 填写表格1 - 基本信息
    table1 = doc.tables[0]
    table1.rows[0].cells[1].text = "九江学院（盖章）"
    table1.rows[1].cells[1].text = project_name
    table1.rows[2].cells[1].text = "（√）重点项目\n（ ）一般项目"
    table1.rows[3].cells[1].text = primary_discipline
    table1.rows[4].cells[1].text = key_area
    table1.rows[5].cells[1].text = team_members['leader']['name']
    table1.rows[6].cells[1].text = "13697973474"
    table1.rows[7].cells[1].text = first_teacher['name']
    table1.rows[8].cells[1].text = "13307928341"
    table1.rows[9].cells[1].text = datetime.datetime.now().strftime('%Y年%m月%d日')

    # 填写表格2 - 详细信息
    table2 = doc.tables[1]

    # 项目名称
    for col in range(5, len(table2.rows[0].cells)):
        table2.rows[0].cells[col].text = project_name

    # 所属一级学科
    for col in range(5, 14):
        table2.rows[1].cells[col].text = primary_discipline

    # 所属二级学科（在第14列开始）
    for col in range(14, 22):
        if table2.rows[1].cells[col].text.strip() == "项目所属\n二级学科":
            continue
        table2.rows[1].cells[col].text = secondary_discipline

    # 项目类型
    for col in range(5, 22):
        if table2.rows[2].cells[col].text.strip().startswith("（）"):
            table2.rows[2].cells[col].text = "（√）重点项目           （  ）一般项目"

    # 所属重点领域
    for col in range(5, 22):
        table2.rows[3].cells[col].text = key_area

    # 项目来源
    table2.rows[4].cells[5].text = project_source

    # 项目实施时间
    start_time = datetime.datetime.now().strftime('%Y年%m月')
    end_time = (datetime.datetime.now() + datetime.timedelta(days=365)).strftime('%Y年%m月')
    for col in range(5, 22):
        table2.rows[6].cells[col].text = f"起始时间：   {start_time}   完成时间：{end_time}"

    # 项目简介（限200字）
    for col in range(2, 22):
        table2.rows[7].cells[col].text = project_intro

    # 团队成员
    # 负责人
    for col in range(2, 22):
        table2.rows[9].cells[col].text = team_members['leader']['name']

    # 成员
    member_names = [m['name'] for m in team_members['members']]
    for row_idx, member_name in enumerate(member_names, start=10):
        for col in range(2, 22):
            table2.rows[row_idx].cells[col].text = member_name

    # 第一指导教师
    for col in range(4, 22):
        if table2.rows[13].cells[col].text.strip() == "姓名":
            table2.rows[13].cells[col].text = first_teacher['name']

    # 指导教师年龄
    for col in range(4, 22):
        if table2.rows[14].cells[col].text.strip() == "年龄":
            table2.rows[14].cells[col].text = first_teacher['age']

    # 指导教师主要成果
    for col in range(4, 22):
        if table2.rows[15].cells[col].text.strip() == "主要成果":
            table2.rows[15].cells[col].text = first_teacher['achievements']
            if len(table2.rows[15].cells) > col + 1:
                table2.rows[16].cells[col + 1].text = "2021年，第十四届全国大学生信息安全竞赛——创新实践能力赛，教育部高等学校网络空间安全专业教学指导委员会，华中赛区二等奖（省级）。"

    # 保存文档
    output_file = f'IntelNexus_已填写_创新创业训练计划项目申报表_{datetime.datetime.now().strftime("%Y%m%d")}.docx'
    doc.save(output_file)

    print("=" * 80)
    print("申报表填写完成！")
    print("=" * 80)
    print(f"\n项目名称：{project_name}")
    print(f"所属学科：{primary_discipline} / {secondary_discipline}")
    print(f"所属领域：{key_area}")
    print(f"项目来源：A（学生自主选题）")
    print(f"\n团队成员：")
    print(f"  负责人：{team_members['leader']['name']}（{team_members['leader']['grade']}, 学号: {team_members['leader']['student_id']}）")
    for i, member in enumerate(team_members['members'], 1):
        print(f"  成员{i}：{member['name']}（{member['grade']}, 学号: {member['student_id']}）")
    print(f"\n指导教师：{first_teacher['name']}（{first_teacher['age']}岁）")
    print(f"\n文档已保存为：{output_file}")
    print("\n注意事项：")
    print("1. 部分团队成员的学号需要补充完整")
    print("2. 需要本人签字的地方请手动签字")
    print("3. 需要盖章的地方请加盖公章")

if __name__ == "__main__":
    fill_intelnexus_application()
