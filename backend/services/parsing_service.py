import logging
from typing import Dict, List
import fitz  # PyMuPDF
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

class ParsingService:
    """
    PDF文档解析服务类
    
    该类提供多种解析策略来提取和构建PDF文档内容，包括：
    - 全文提取
    - 逐页解析
    - 基于标题的分段
    - 文本和表格混合解析
    """

    def parse_pdf(self, text: str, method: str, metadata: dict, page_map: list = None, file_path: str = None) -> dict:
        """
        使用指定方法解析PDF文档

        参数:
            text (str): PDF文档的文本内容
            method (str): 解析方法 ('all_text', 'by_pages', 'by_titles', 或 'text_and_tables')
            metadata (dict): 文档元数据，包括文件名和其他属性
            page_map (list): 包含每页内容和元数据的字典列表
            file_path (str, optional): 原始 PDF 文件的路径，用于支持 pdfplumber 提取表格等需要原文件的操作

        返回:
            dict: 解析后的文档数据，包括元数据和结构化内容

        异常:
            ValueError: 当page_map为空或指定了不支持的解析方法时抛出
        """
        try:
            if not page_map:
                raise ValueError("Page map is required for parsing.")
            
            parsed_content = []
            total_pages = len(page_map)
            
            if method == "all_text":
                parsed_content = self._parse_all_text(page_map)
            elif method == "by_pages":
                parsed_content = self._parse_by_pages(page_map)
            elif method == "by_titles":
                parsed_content = self._parse_by_titles(page_map)
            elif method == "text_and_tables":
                parsed_content = self._parse_text_and_tables(page_map, file_path)
            elif method == "titles_and_tables":
                parsed_content = self._parse_titles_and_tables(page_map, file_path)
            else:
                raise ValueError(f"Unsupported parsing method: {method}")
                
            # Final cleanup: Remove empty sections that might be caused by aggressive formula filtering
            cleaned_content = []
            for item in parsed_content:
                if item["type"] == "section" and not item["content"].strip():
                    continue # Skip empty sections
                cleaned_content.append(item)
            parsed_content = cleaned_content
                
            # Create document-level metadata
            document_data = {
                "metadata": {
                    "filename": metadata.get("filename", ""),
                    "total_pages": total_pages,
                    "parsing_method": method,
                    "timestamp": datetime.now().isoformat()
                },
                "content": parsed_content
            }
            
            return document_data
            
        except Exception as e:
            logger.error(f"Error in parse_pdf: {str(e)}")
            raise

    def _parse_all_text(self, page_map: list) -> list:
        """
        将文档中的所有文本内容提取为连续流

        参数:
            page_map (list): 包含每页内容的字典列表

        返回:
            list: 包含带页码的文本内容的字典列表
        """
        return [{
            "type": "Text",
            "content": page["text"],
            "page": page["page"]
        } for page in page_map]

    def _parse_by_pages(self, page_map: list) -> list:
        """
        逐页解析文档，保持页面边界

        参数:
            page_map (list): 包含每页内容的字典列表

        返回:
            list: 包含带页码的分页内容的字典列表
        """
        parsed_content = []
        for page in page_map:
            parsed_content.append({
                "type": "Page",
                "page": page["page"],
                "content": page["text"]
            })
        return parsed_content

    def _parse_by_titles(self, page_map: list) -> list:
        """
        通过识别标题来解析文档并将内容组织成章节

        改进后的混合判定方法：
        1. 依赖底层工具传来的元数据（如果使用了 unstructured 且标记为 Title）
        2. 基于正则表达式匹配常见章节序号（如 "1. "，"1.1 "，"第x章"，"Abstract"，"Introduction"）
        3. 字体特征（如果加载器提供了字体大小和粗细信息）
        4. 保留原有的大写短句启发式判断（作为后备）

        参数:
            page_map (list): 包含每页内容的字典列表

        返回:
            list: 包含带标题和页码的分章节内容的字典列表
        """
        import re
        from collections import Counter
        
        parsed_content = []
        current_title = "Document Start" # 默认初始标题，防止文档开头没有标题的内容丢失
        current_content = []
        current_page = page_map[0]["page"] if page_map else 1

        # 常见的标题正则表达式模式
        title_patterns = [
            r"^(Abstract|Introduction|Conclusion|References|References?)$",
            r"^(ABSTRACT|INTRODUCTION|CONCLUSION|REFERENCES)$",
            r"^第[一二三四五六七八九十百千万]+[章节部分][\s\S]*$",
            r"^\d+\.\s+[A-Z]",
            r"^\d+\.\d+\s+[A-Z]",
            r"^\d{1,2}[\.\s]+[\u4e00-\u9fa5]+",
            r"^[IVXLCDM]+\.\s+[A-Z]"
        ]

        def is_title(line: str, metadata: dict = None) -> bool:
            line_clean = line.strip()
            if not line_clean:
                return False
                
            # 1. 绝对一票否决门槛 (严格剔除公式)
            # 不可能以小写字母、标点符号等开头
            if not re.match(r'^[A-Z0-9\u4e00-\u9fa5]', line_clean):
                return False
                
            # 包含明显的等式或特殊数学符号
            if re.search(r'(=|≈|≤|≥|∈|∑|∫|∥|×|÷)', line_clean):
                return False
                
            # 以公式编号结尾，如 (1), (5)
            if re.search(r'\(\d+\)$', line_clean):
                return False

            # 2. 启发式特征判定
            letters_and_chinese = re.findall(r'[a-zA-Z\u4e00-\u9fa5]', line_clean)
            alphanumeric = re.findall(r'[a-zA-Z0-9\u4e00-\u9fa5]', line_clean)
            
            if len(line_clean) > 0 and (len(alphanumeric) / len(line_clean)) < 0.5:
                return False
            if len(letters_and_chinese) < 3:
                return False

            # 3. 如果 unstructured 明确标记为 Title，需严格复核
            if metadata and metadata.get("category") == "Title":
                if not re.search(r'[\_\^\|\\]', line_clean):
                    words = [w for w in line_clean.split() if re.match(r'[a-zA-Z]+', w)]
                    capitalized = [w for w in words if w and w[0].isupper()]
                    if words and len(capitalized) > 0:
                        return True
                    if not words: # 纯中文或数字
                        return True
                
            # 4. 正向正则白名单
            for pattern in title_patterns:
                if re.match(pattern, line_clean, re.IGNORECASE if "abstract" in pattern.lower() else 0):
                    if len(line_clean) < 100:
                        return True
                        
            # 5. 后备机制：全大写短句
            if len(line_clean) < 60 and line_clean.isupper() and re.search(r'[A-Z]', line_clean):
                if len(line_clean.split()) > 1:
                    return True
                
            return False

        for page in page_map:
            # 如果是由 unstructured 提取的（一页包含多个切分好的 element）
            # 这时 page["text"] 可能只是一个句子，而不是整页的文本
            # 检查是否有附加的 metadata 帮助判断
            metadata = page.get("metadata", {})
            
            # 如果这是一个单独的元素（unstructured 返回的格式）
            if "element_type" in metadata:
                text_content = page["text"]
                
                # 特殊处理：如果是 unstructured 识别的表格 (Table) 或者是图片文本 (FigureCaption)
                category = metadata.get("category", "")
                if category in ["Table", "FigureCaption"]:
                    
                    # 智能抢救：如果当前普通文本的最后一行/几行是以 "Table" 或 "Figure" 开头的描述，把它抠出来
                    extracted_caption = ""
                    if current_content:
                        # 检查倒数第一行或拼接后的最后一段
                        last_text = current_content[-1]
                        if re.match(r'^(Table|Figure|图|表)[\s\d\.\:]+', last_text, re.IGNORECASE):
                            extracted_caption = last_text
                            current_content.pop() # 从正文中抠除

                    # 先把当前正在累积的剩余普通文本保存下来
                    if current_content:
                        parsed_content.append({
                            "type": "section",
                            "title": current_title,
                            "content": '\n'.join(current_content).strip(),
                            "page": current_page
                        })
                        current_content = []
                        
                    content_to_save = text_content.strip()
                    if extracted_caption:
                        content_to_save = extracted_caption + "\n" + content_to_save

                    # --- 智能粘合逻辑 ---
                    
                    # 情况1：当前是 Table，上一个是 FigureCaption
                    if category == "Table" and parsed_content and parsed_content[-1]["type"] == "figurecaption":
                        # 将上一个 Caption 吸收到当前 Table 中，类型改为 table
                        prev_caption = parsed_content[-1]["content"]
                        parsed_content[-1]["type"] = "table"
                        parsed_content[-1]["content"] = prev_caption + "\n" + content_to_save
                        
                    # 情况2：当前是 FigureCaption，上一个是 Table
                    elif category == "FigureCaption" and parsed_content and parsed_content[-1]["type"] == "table":
                        # 将当前的 Caption 追加到前面的 Table 后面
                        parsed_content[-1]["content"] += "\n" + content_to_save
                        
                    # 情况3：当前是 FigureCaption，上一个也是 FigureCaption
                    elif category == "FigureCaption" and parsed_content and parsed_content[-1]["type"] == "figurecaption":
                        parsed_content[-1]["content"] += "\n" + content_to_save
                        
                    # 默认情况：独立成块
                    else:
                        parsed_content.append({
                            "type": category.lower(),
                            "title": current_title,
                            "content": content_to_save,
                            "page": page["page"]
                        })
                    continue

                if is_title(text_content, metadata):
                    # 保存上一个 section
                    if current_content:
                        parsed_content.append({
                            "type": "section",
                            "title": current_title,
                            "content": '\n'.join(current_content).strip(),
                            "page": current_page
                        })
                    current_title = text_content.strip()
                    current_content = []
                    current_page = page["page"]
                else:
                    if text_content.strip():
                        current_content.append(text_content)
            
            # 如果是普通的整页文本提取（pymupdf / pypdf 返回的格式）
            else:
                lines = page["text"].split('\n')
                for line in lines:
                    if is_title(line, metadata):
                        # 保存上一个 section
                        if current_content:
                            parsed_content.append({
                                "type": "section",
                                "title": current_title,
                                "content": '\n'.join(current_content).strip(),
                                "page": current_page
                            })
                        current_title = line.strip()
                        current_content = []
                        current_page = page["page"]
                    else:
                        if line.strip():
                            current_content.append(line)

        # 添加最后一个 section
        if current_content:
            parsed_content.append({
                "type": "section",
                "title": current_title,
                "content": '\n'.join(current_content).strip(),
                "page": current_page
            })

        return parsed_content

    def _parse_text_and_tables(self, page_map: list, file_path: str = None) -> list:
        """
        通过分离文本和表格内容来解析文档

        使用 pdfplumber 真正提取表格结构：
        1. 首先从原始 PDF 中提取出表格的二维结构，转为 Markdown 表格
        2. 然后再处理剩余的文本。

        参数:
            page_map (list): 包含每页内容的字典列表（用于文本后备）
            file_path (str): PDF 的原始路径，供 pdfplumber 使用

        返回:
            list: 包含分离的文本和表格内容（带页码）的字典列表
        """
        parsed_content = []
        
        if not file_path:
            logger.warning("No file_path provided for _parse_text_and_tables, falling back to basic text parsing.")
            return self._parse_by_pages(page_map)

        try:
            import pdfplumber
            
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # 1. 尝试提取这页的表格
                    tables = page.extract_tables()
                    
                    if tables:
                        # 对于找到的每个表格，将其转换为 Markdown 格式
                        for table in tables:
                            md_table = []
                            for row_idx, row in enumerate(table):
                                # 清理并格式化每行的数据
                                clean_row = [str(cell).replace('\n', ' ').strip() if cell else "" for cell in row]
                                md_row = "| " + " | ".join(clean_row) + " |"
                                md_table.append(md_row)
                                
                                # 在表头后加上 Markdown 的分隔线
                                if row_idx == 0:
                                    separator = "| " + " | ".join(["---" for _ in row]) + " |"
                                    md_table.append(separator)
                                    
                            if md_table:
                                md_table_str = '\n'.join(md_table)
                                import re
                                text_only = re.sub(r'[\s\|\-]', '', md_table_str)
                                if len(text_only) > 5:
                                    parsed_content.append({
                                        "type": "table",
                                        "title": f"Table on Page {page_num}",
                                        "content": md_table_str,
                                        "page": page_num
                                    })
                                
                    # 2. 提取除表格外的普通文本（简化处理，直接提取文本）
                    # pdfplumber 提取文本有时候会带出表格里的文字，
                    # 理想情况下可以 mask 掉表格区域再提取文本。
                    text = page.extract_text()
                    if text and text.strip():
                        # 为了避免完全重复，如果这页有表格，我们简单说明一下
                        # (在严谨的RAG里，会从 text 中剔除掉 table 里的文字)
                        parsed_content.append({
                            "type": "text",
                            "content": text.strip(),
                            "page": page_num
                        })
                        
        except Exception as e:
            logger.error(f"Error parsing tables with pdfplumber: {str(e)}")
            # Fallback to basic text
            return self._parse_by_pages(page_map)
            
        return parsed_content

    def _parse_titles_and_tables(self, page_map: list, file_path: str = None) -> list:
        """
        结合标题解析和表格提取的高级方法（已去除非必需的 pdfplumber）。
        主要服务于 unstructured hi_res 的输出：
        1. 使用正则表达式和元数据来识别章节标题。
        2. 当遇到 unstructured 识别的 Table 时，提取其 metadata.text_as_html 作为表格内容。
        3. 将图表文本单独归类，防止污染正文文本。
        """
        import re
        
        raw_parsed_content = []
        current_title = "Document Start"
        current_content = []
        current_page = page_map[0].get("page", 1) if page_map else 1

        # 常见的标题正则表达式模式
        title_patterns = [
            r"^(Abstract|Introduction|Conclusion|References|References?)$",
            r"^(ABSTRACT|INTRODUCTION|CONCLUSION|REFERENCES)$",
            r"^第[一二三四五六七八九十百千万]+[章节部分][\s\S]*$",
            r"^\d+\.\s+[A-Z]",
            r"^\d+\.\d+\s+[A-Z]",
            r"^\d{1,2}[\.\s]+[\u4e00-\u9fa5]+",
            r"^[IVXLCDM]+\.\s+[A-Z]"
        ]

        def is_title(line: str, metadata: dict = None) -> bool:
            """
            极简且稳健的标题判断逻辑：
            完全摒弃字体特征，改为“正向严格白名单认证”。
            """
            line_clean = line.strip()
            if not line_clean:
                return False
                
            # 1. 绝对一票否决门槛 (严格剔除公式)
            if not re.match(r'^[A-Z0-9\u4e00-\u9fa5]', line_clean):
                return False
            if re.search(r'(=|≈|≤|≥|∈|∑|∫|∥|×|÷)', line_clean):
                return False
            if re.search(r'\(\d+\)$', line_clean):
                return False

            # 2. 启发式特征判定
            letters_and_chinese = re.findall(r'[a-zA-Z\u4e00-\u9fa5]', line_clean)
            alphanumeric = re.findall(r'[a-zA-Z0-9\u4e00-\u9fa5]', line_clean)
            
            if len(line_clean) > 0 and (len(alphanumeric) / len(line_clean)) < 0.5:
                return False
            if len(letters_and_chinese) < 3:
                return False

            # 3. 如果 unstructured 明确标记为 Title，需严格复核
            if metadata and metadata.get("category") == "Title":
                if not re.search(r'[\_\^\|\\]', line_clean):
                    words = [w for w in line_clean.split() if re.match(r'[a-zA-Z]+', w)]
                    capitalized = [w for w in words if w and w[0].isupper()]
                    if words and len(capitalized) > 0:
                        return True
                    if not words:
                        return True
                
            # 4. 正向正则白名单
            for pattern in title_patterns:
                if re.match(pattern, line_clean, re.IGNORECASE if "abstract" in pattern.lower() else 0):
                    if len(line_clean) < 100:
                        return True
                        
            # 5. 后备：全大写的纯英文短句
            if len(line_clean) < 60 and line_clean.isupper() and re.search(r'[A-Z]', line_clean):
                if not any(char.isdigit() for char in line_clean):
                    if len(line_clean.split()) > 1:
                        return True
                
            return False

        for page in page_map:
            page_num = page.get("page", 1)
            metadata = page.get("metadata", {})
            
            # 1. 提取并分组文本
            if "element_type" in metadata:
                text_content = page.get("text", "")
                
                # 如果是 unstructured 原生识别出的 Table 或 FigureCaption
                # 我们把它作为独立的块输出，防止其文本污染普通段落
                category = metadata.get("category", "")
                if category in ["Table", "FigureCaption"]:
                    
                    # 精准抢救：如果当前普通文本的最后一段是以 "Table 1:" 或 "Figure 1." 开头，
                    # 并且字数不算极其冗长（真正的caption），把它抠出来作为描述。
                    extracted_caption = ""
                    if current_content:
                        last_text = current_content[-1].strip()
                        # 必须是 Table/Figure/图/表 + 数字 + 冒号/点
                        if re.match(r'^(Table|Figure|图|表)\s*\d+[\.\:]', last_text, re.IGNORECASE):
                            if len(last_text.split()) < 150 and len(last_text) < 1000:
                                # 如果当前是 Table，只抢救 Table 的标题
                                is_table_cap = re.match(r'^(Table|表)', last_text, re.IGNORECASE)
                                if (category == "Table" and is_table_cap) or (category == "FigureCaption"):
                                    extracted_caption = last_text
                                    current_content.pop()

                    if current_content:
                        raw_parsed_content.append({
                            "type": "section",
                            "title": current_title,
                            "content": '\n'.join(current_content).strip(),
                            "page": current_page
                        })
                        current_content = []
                    
                    # 针对表格，优先提取 hi_res 模式下自带的 text_as_html 属性
                    content_to_save = text_content.strip()
                    if category == "Table" and metadata.get("text_as_html"):
                        content_to_save = metadata.get("text_as_html")
                        
                    if extracted_caption:
                        content_to_save = extracted_caption + "\n\n" + content_to_save

                    # 判断当前块是不是一个明确的新标题（防止两个独立的标题被强行合并）
                    is_new_explicit_caption = bool(re.match(r'^(Table|TABLE|Figure|FIGURE|图|表)\s*\d+[\.\:]', content_to_save, re.IGNORECASE))

                    # --- 智能粘合逻辑 ---
                    
                    if category == "Table" and raw_parsed_content and raw_parsed_content[-1]["type"] == "figurecaption":
                        prev_caption = raw_parsed_content[-1]["content"]
                        # 如果前一个其实是 Figure 的标题，就不能被 Table 吸附
                        if not re.match(r'^(Figure|图)\s*\d+[\.\:]', prev_caption, re.IGNORECASE):
                            raw_parsed_content[-1]["type"] = "table"
                            raw_parsed_content[-1]["content"] = prev_caption + "\n\n" + content_to_save
                        else:
                            raw_parsed_content.append({
                                "type": "table",
                                "title": current_title,
                                "content": content_to_save,
                                "page": page_num
                            })

                    elif category == "Table" and raw_parsed_content and raw_parsed_content[-1]["type"] == "table":
                        # 连续的 Table 块，这通常是由于一个大表被切分，或是表格的标题(Caption)被误判为了独立的 Table
                        if not is_new_explicit_caption:
                            raw_parsed_content[-1]["content"] += "\n\n" + content_to_save
                        else:
                            raw_parsed_content.append({
                                "type": "table",
                                "title": current_title,
                                "content": content_to_save,
                                "page": page_num
                            })

                    elif category == "FigureCaption" and raw_parsed_content and raw_parsed_content[-1]["type"] == "table":
                        # 如果这个 FigureCaption 明明写着 Figure，就不能合并到前面的 Table 中
                        if re.match(r'^(Figure|图)\s*\d+[\.\:]', content_to_save, re.IGNORECASE):
                            raw_parsed_content.append({
                                "type": "figurecaption",
                                "title": current_title,
                                "content": content_to_save,
                                "page": page_num
                            })
                        else:
                            raw_parsed_content[-1]["content"] += "\n\n" + content_to_save
                        
                    elif category == "FigureCaption" and raw_parsed_content and raw_parsed_content[-1]["type"] == "figurecaption":
                        # 只有当它不是一个崭新的标题时，才认为是长标题被切碎，进行无缝拼接
                        if not is_new_explicit_caption:
                            raw_parsed_content[-1]["content"] += "\n" + content_to_save
                        else:
                            raw_parsed_content.append({
                                "type": "figurecaption",
                                "title": current_title,
                                "content": content_to_save,
                                "page": page_num
                            })
                        
                    else:
                        raw_parsed_content.append({
                            "type": category.lower(),
                            "title": current_title,
                            "content": content_to_save,
                            "page": page_num
                        })
                    continue

                if is_title(text_content, metadata):
                    if current_content:
                        raw_parsed_content.append({
                            "type": "section",
                            "title": current_title,
                            "content": '\n'.join(current_content).strip(),
                            "page": current_page
                        })
                    current_title = text_content.strip()
                    current_content = []
                    current_page = page_num
                else:
                    if text_content.strip():
                        # 尝试识别未被正确分类为 Table/FigureCaption 的标题段落
                        if re.match(r'^(Figure|Table|图|表)\s*\d+[\.\:]', text_content.strip(), re.IGNORECASE):
                            if current_content:
                                raw_parsed_content.append({
                                    "type": "section",
                                    "title": current_title,
                                    "content": '\n'.join(current_content).strip(),
                                    "page": current_page
                                })
                                current_content = []
                                
                            block_type = "figurecaption" if re.match(r'^(Figure|图)', text_content.strip(), re.IGNORECASE) else "table"
                            raw_parsed_content.append({
                                "type": block_type,
                                "title": current_title,
                                "content": text_content.strip(),
                                "page": page_num
                            })
                        else:
                            current_content.append(text_content)
            else:
                lines = page.get("text", "").split('\n')
                for line in lines:
                    if is_title(line, metadata):
                        if current_content:
                            raw_parsed_content.append({
                                "type": "section",
                                "title": current_title,
                                "content": '\n'.join(current_content).strip(),
                                "page": current_page
                            })
                        current_title = line.strip()
                        current_content = []
                        current_page = page_num
                    else:
                        if line.strip():
                            current_content.append(line)
        
        # 添加最后剩余的段落
        if current_content:
            raw_parsed_content.append({
                "type": "section",
                "title": current_title,
                "content": '\n'.join(current_content).strip(),
                "page": current_page
            })

        # --- 后处理：合并同一 Title 下被图表打断的 Section 文本 ---
        # 我们遍历 raw_parsed_content，把属于同一个 title 的所有 type="section" 的块合并。
        # 图表 (table/figurecaption) 依然作为独立的块保留在原本的位置。
        parsed_content = []
        section_buffers = {} # 记录每个 title 下正在积累的 section

        for block in raw_parsed_content:
            title = block["title"]
            b_type = block["type"]
            
            if b_type == "section":
                if title not in section_buffers:
                    section_buffers[title] = block
                    parsed_content.append(section_buffers[title])
                else:
                    # 如果该标题已经有 section 存在，将其文本追加，这样被图表隔开的段落就能无缝衔接
                    section_buffers[title]["content"] +=  block["content"]
            else:
                # 遇到 table 或 figurecaption，直接放入结果列表中，保持独立
                parsed_content.append(block)

        return parsed_content
