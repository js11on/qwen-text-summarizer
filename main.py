import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 初始化阿里百炼Qwen模型
llm = ChatOpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url=os.getenv("BASE_URL"),
    model=os.getenv("MODEL_NAME"),
    temperature=0.3
)

def summarize_text(long_text: str, mode: str = "short") -> str:
    """
    文本摘要函数
    :param long_text: 需要总结的原文
    :param mode: short简短摘要 / detail详细摘要
    :return: 摘要结果
    """
    if mode == "short":
        prompt = f"""
请对下面这段文字进行简短摘要，控制在100字以内，保留核心信息：
{long_text}
        """
    else:
        prompt = f"""
请对下面这段文字做详细摘要，梳理文章的层次、核心观点，300字左右：
{long_text}
        """
    response = llm.invoke(prompt)
    return response.content


if __name__ == "__main__":
    print("===== 通义千问文本摘要工具 =====")
    print("模式：short=简短摘要，detail=详细摘要 | 输入exit退出\n")
    while True:
        mode = input("请选择摘要模式(short/detail)：")
        if mode.lower() == "exit":
            break
        content = input("粘贴需要总结的长文本：\n")
        if content.lower() == "exit":
            break
        result = summarize_text(content, mode)
        print("\n===== 生成摘要 =====")
        print(result)
        print("\n---------------------------\n")
