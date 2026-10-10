import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

def init_llm():
    api_key = os.getenv("DASHSCOPE_API_KEY")
    base_url = os.getenv("BASE_URL")
    model = os.getenv("MODEL_NAME")
    if not all([api_key, base_url, model]):
        raise RuntimeError("环境变量缺失，请检查.env文件配置")
    llm = ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model,
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
        system_prompt = "你是文本摘要助手，输出详细摘要，完整保留文章关键逻辑、要点，条理清晰。"
    return ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "请对下面文本做摘要：{text}")
    ])

def summarize_text(llm, content: str, summary_type:str):
    prompt = get_prompt_by_type(summary_type)
    chain = prompt | llm
    resp = chain.invoke({"text": content})
    return resp.content

# ========== 【新增函数】长文本分段处理 ==========
def split_text(text: str, chunk_size=1200, overlap=150):
    """文本分段，带重叠，防止上下文断裂"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += (chunk_size - overlap)
    return chunks

def long_text_summary(llm, content: str, summary_type: str):
    """长文本：分段摘要，最后汇总"""
    chunks = split_text(content)
    print(f"\n✅ 文本自动切分为 {len(chunks)} 段，开始分段摘要...")
    part_summaries = []
    for idx, chunk in enumerate(chunks):
        print(f"\n---正在处理第{idx+1}/{len(chunks)}段---")
        part_sum = summarize_text(llm, chunk, summary_type)
        part_summaries.append(part_sum)
        print(f"分段{idx+1}摘要：{part_sum}")

    # 汇总所有分段摘要，生成最终总摘要
    print("\n🧩 正在合并所有分段结果，生成全文总摘要...")
    combine_prompt = ChatPromptTemplate.from_messages([
        ("system", "你是文本摘要助手，将下面多段摘要整合成一份连贯完整的摘要，不要重复。"),
        ("human", "各分段摘要内容：{part_sums}，输出最终全文摘要")
    ])
    combine_chain = combine_prompt | llm
    final_sum = combine_chain.invoke({"part_sums": "\n".join(part_summaries)})
    return final_sum.content

def read_txt_file(file_path: str):
    """读取本地txt文件"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="gbk") as f:
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
    print("3: 【新增】长文本txt自动分段摘要")
    choice = input("请选择模式(1/2/3):")

    # 选择摘要风格
    print("\n请选择摘要类型：")
    print("1 - 简短摘要")
    print("2 - 详细摘要")
    style_choice = input("输入1或2：")
    summary_type = "short" if style_choice == "1" else "detail"

    result = ""
    if choice == "1":
        text = input("请输入需要摘要的文本：\n")
        result = summarize_text(llm, text, summary_type)
    elif choice == "2":
        path = input("输入txt文件完整路径：")
        txt_content = read_txt_file(path)
        if txt_content.startswith("读取文件失败"):
            print(txt_content)
        else:
            result = summarize_text(llm, txt_content, summary_type)
    elif choice == "3":
        path = input("输入长文本txt文件完整路径：")
        txt_content = read_txt_file(path)
        if txt_content.startswith("读取文件失败"):
            print(txt_content)
        else:
            result = long_text_summary(llm, txt_content, summary_type)
    else:
        print("输入选项错误")
        exit()

    print("\n===== 最终摘要结果 =====")
    print(result)
    save_result(result)
