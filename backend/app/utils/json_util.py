import json
import re

def repair_truncated_json(json_str: str) -> str:
    """
    尝试修复被截断的 JSON 字符串
    
    Args:
        json_str: 可能被截断的 JSON 字符串
        
    Returns:
        修复后的 JSON 字符串
    """
    json_str = json_str.strip()
    
    # 如果已经是有效的 JSON，直接返回
    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        pass
    
    # 尝试修复常见的截断问题
    repaired = json_str
    
    # 1. 修复未闭合的字符串（在字符串中间被截断）
    # 找到最后一个未转义的引号
    last_quote = repaired.rfind('"')
    if last_quote > 0:
        # 检查这个引号是否被转义
        escape_count = 0
        i = last_quote - 1
        while i >= 0 and repaired[i] == '\\':
            escape_count += 1
            i -= 1
        
        # 如果引号未被转义（偶数个反斜杠），说明字符串未闭合
        if escape_count % 2 == 0:
            # 在最后一个引号后添加闭合引号
            repaired = repaired[:last_quote + 1]
    
    # 2. 移除最后一个不完整的键值对
    # 查找最后一个完整的键值对
    patterns_to_try = [
        r',\s*"[^"]*"\s*:\s*$',  # 最后一个不完整的键
        r',\s*"[^"]*"\s*:\s*"[^"]*$',  # 最后一个不完整的字符串值
        r',\s*"[^"]*"\s*:\s*\[[^\]]*$',  # 最后一个不完整的数组
        r',\s*"[^"]*"\s*:\s*\{[^}]*$',  # 最后一个不完整的对象
    ]
    
    for pattern in patterns_to_try:
        match = re.search(pattern, repaired)
        if match:
            repaired = repaired[:match.start()]
            break
    
    # 3. 统计未闭合的括号并添加闭合
    open_braces = repaired.count('{') - repaired.count('}')
    open_brackets = repaired.count('[') - repaired.count(']')
    
    # 添加缺失的闭合括号
    repaired += ']' * open_brackets + '}' * open_braces
    
    return repaired

def check_json(json_str: str, schema: str | dict) -> tuple[bool, str]:
    """
    根据模板 JSON 校验目标字符串的格式是否符合要求
    
    Args:
        json_str: 要校验的 JSON 字符串
        schema: 模板 JSON 字符串或字典对象，用于定义预期的数据结构
        
    Returns:
        tuple[bool, str]: (是否验证通过, 错误信息)
        如果验证通过返回 (True, "")，否则返回 (False, 错误原因)
    """
    try:
        # 解析输入的 JSON 字符串
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return False, f"JSON 解析错误: {str(e)}"
        
        # 处理 schema 参数
        try:
            if isinstance(schema, str):
                schema = json.loads(schema)
            elif not isinstance(schema, dict):
                return False, "schema 必须是 JSON 字符串或字典对象"
        except json.JSONDecodeError as e:
            return False, f"schema 解析错误: {str(e)}"
        
        def check_structure(target, template, path=""):
            # 处理数字类型（int 和 float 可以互换）
            if isinstance(template, (int, float)) and isinstance(target, (int, float)):
                return True, ""
                
            # 检查基本数据类型
            if type(template) != type(target) and not (isinstance(template, (int, float)) and isinstance(target, (int, float))):
                return False, f"路径 '{path}' 的类型不匹配: 期望 {type(template).__name__}, 实际 {type(target).__name__}"
                
            # 如果是列表类型
            if isinstance(template, list):
                if not template:  # 如果模板列表为空，则允许任何列表
                    return True, ""
                if not target:  # 如果目标列表为空，但模板不为空
                    return False, f"路径 '{path}' 的列表为空，但期望有内容"
                    
                # 检查列表中的每个元素是否符合模板中第一个元素的格式
                template_item = template[0]
                for i, item in enumerate(target):
                    is_valid, error = check_structure(item, template_item, f"{path}[{i}]")
                    if not is_valid:
                        return False, error
                return True, ""
                
            # 如果是字典类型
            elif isinstance(template, dict):
                # 检查所有必需的键是否存在，并且值的类型是否正确
                for key in template:
                    if key not in target:
                        return False, f"路径 '{path}' 缺少必需的键 '{key}'"
                    is_valid, error = check_structure(target[key], template[key], f"{path}.{key}")
                    if not is_valid:
                        return False, error
                return True, ""
                
            # 对于其他基本类型，返回 True
            return True, ""
                
        is_valid, error = check_structure(data, schema)
        return is_valid, error if not is_valid else ""
        
    except Exception as e:
        return False, f"未预期的错误: {str(e)}"