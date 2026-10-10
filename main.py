import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

def init_llm():
    llm = ChatOpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url=os.getenv("BASE_URL"),
        model=os.getenv("MODEL_NAME"),
        temperature=0.3
    )
    return llm

def get_prompt_by_type(summary_type: str):
    """根据用户选择返回不同提示词"""
    if summary_type == "short":
        # 简短摘要
        system_prompt = "你是文本摘要助手，输出简短摘要，控制在100字以内，只保留核心要点。"
    else:
        # 详细摘要
        system_prompt = "你是文本摘要助手，输出详细摘要，完整保留文章的关键逻辑、技术点与项目信息，条理清晰。"
    return ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "请对下面文本做摘要：{text}")
    ])

def summarize_text(llm, content: str, summary_type:str):
    prompt = get_prompt_by_type(summary_type)
    chain = prompt | llm
    resp = chain.invoke({"text": content})
    return resp.content

def read_txt_file(file_path: str):
    """读取本地txt文件"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"读取文件失败：{str(e)}"

def save_result(summary: str):
    """保存摘要到result.txt"""
    with open("result.txt", "w", encoding="utf-8") as f:
        f.write(summary)
    print("\n✅ 摘要已自动保存至 result.txt")


if __name__ == "__main__":
    llm = init_llm()
    print("===== 文本摘要工具 =====")
    print("1: 手动输入文本摘要")
    print("2: 读取本地txt文件摘要")
    choice = input("请选择模式(1/2):")

    # 新增：选择摘要风格
    print("\n请选择摘要类型：")
    print("1 - 简短摘要")
    print("2 - 详细摘要")
    style_choice = input("输入1或2：")
    summary_type = "short" if style_choice == "1" else "detail"

    if choice == "1":
        text = input("请输入需要摘要的文本：\n")
        res = summarize_text(llm, text, summary_type)
        print("\n=====摘要结果=====")
        print(res)
        save_result(res)

    elif choice == "2":
        path = input("输入txt文件完整路径：")
        txt_content = read_txt_file(path)
        if txt_content.startswith("读取文件失败"):
            print(txt_content)
        else:
            res = summarize_text(llm, txt_content, summary_type)
            print("\n=====摘要结果=====")
            print(res)
            save_result(res)
    else:
        print("输入选项错误")
