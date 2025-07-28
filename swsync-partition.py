import os
import chardet
import re
import sys

def getclassrep_func(cpp_content, class_name):
    result = []
    func_regex = r"\b" + class_name + r"::\w+\b"
    func_pattern = re.compile(func_regex)
    idx = 0
    while True:
        match = func_pattern.search(cpp_content, idx)
        if not match:
            break
        func_start = match.start()
        line_start = cpp_content.rfind("\n", 0, func_start) + 1
        line_end = cpp_content.find("\n", func_start)
        line = cpp_content[line_start:line_end].strip()
        ret_type, func_name = line.split("::")[0], match.group()
        code_start = cpp_content.find("{", match.end())
        stack = ["{"]  
        code_end = code_start + 1
        while stack:
            if cpp_content[code_end] == "{":
                stack.append("{")
            elif cpp_content[code_end] == "}":
                stack.pop()
            code_end += 1
        addlis = f"{ret_type} {class_name}::{cpp_content[func_start:code_end].strip()}"
        addlis = addlis.replace(class_name+" "+class_name+"::", "")
        result.append(addlis)
        idx = code_end  
    return "\n".join(result)


def get_classtype_for_class(class_name):
    for prefix, mapped_type in prefix_mapping:
        if class_name.startswith(prefix):
            return mapped_type
    return DEFAULT_CLASSTYPE


def process_class_name(class_name):
    for prefix, mapped_type in prefix_mapping:
        if class_name.startswith(prefix):
            suffix = class_name[len(prefix):]
            if suffix:
                suffix_lower = suffix[0].lower() + suffix[1:].lower()
            else:
                suffix_lower = ""
            return f"{mapped_type}-{suffix_lower}"
    return class_name.lower()


def separate_classes(header_file_path):
    split_files = []
    
    # 保存原始文件名（不含扩展名）用于后续判断
    original_basename = os.path.basename(header_file_path).replace(".hpp", "")
    original_filename = os.path.basename(header_file_path)
    
    if ".cpp" in header_file_path:
        header_file_path = header_file_path.replace(".cpp", ".hpp")
    cpp_file_path = header_file_path.replace(".hpp", ".cpp")
    original_header_basename = os.path.basename(header_file_path)
    
    if not os.path.exists(header_file_path):
        print(f"Error: 头文件不存在 - {header_file_path}", file=sys.stderr)
        return []
    if not os.path.exists(cpp_file_path):
        print(f"Error: 源文件不存在 - {cpp_file_path}", file=sys.stderr)
        return []
    
    header_encoding = check_codes(header_file_path)
    cpp_encoding = check_codes(cpp_file_path)
    filenameClass = os.path.basename(header_file_path).replace(".hpp", "").replace("-", "")
    print(f"The original class name of the file may be (lowercase):{filenameClass}", file=sys.stdout)
    
    # 创建缓存目录
    new_dir_name = cache_dir
    if not os.path.exists(new_dir_name):
        os.makedirs(new_dir_name)
    
    with open(header_file_path, 'r', encoding=header_encoding) as f:
        header_content = f.read()
    header_includes = re.findall(r'^\s*#include\s+["<].*?[">]\s*$', header_content, re.MULTILINE)
    header_includes_str = "\n".join(header_includes) + "\n" if header_includes else ""
    
    with open(cpp_file_path, 'r', encoding=cpp_encoding) as f:
        cpp_content = f.read()
    # 提取所有#include
    cpp_includes = re.findall(r'^\s*#include\s+["<].*?[">]\s*$', cpp_content, re.MULTILINE)

    filtered_cpp_includes = []
    for include in cpp_includes:
        include_filename = re.findall(r'["<](.*?)[">]', include)[0] 
        if os.path.basename(include_filename) != original_header_basename:
            filtered_cpp_includes.append(include)
    filtered_cpp_includes_str = "\n".join(filtered_cpp_includes) + "\n" if filtered_cpp_includes else ""
    
    final_endif = ""
    endif_match = re.search(r"\n#endif\s*$", header_content)
    if endif_match:
        final_endif = endif_match.group()
        header_content = header_content[:endif_match.start()]
    
    # 分割类定义
    class_parts = header_content.split('class ')
    class_parts = [part.strip() for part in class_parts if part.strip()]
    include_list = []
    other_headers = []  # 存储其他分离出的头文件
    
    # 首先收集所有将要生成的头文件
    for i, class_part in enumerate(class_parts):
        if ';' in class_part and '{' not in class_part:  # 跳过前置声明
            continue
        
        class_name = class_part.split()[0]
        if "#ifndef" in class_part and "#define" in class_part:
            include_list = class_part
            continue
        
        if class_name.lower() == filenameClass:
            continue
            
        processed_name = process_class_name(class_name)
        other_headers.append(f"{processed_name}.hpp")
    
    # 生成包含其他头文件的语句
    other_headers_include = "\n".join([f"#include \"{header}\"" for header in other_headers]) + "\n"
    
    print("Other header files that need to be included in main header:"+other_headers_include, file=sys.stdout)
    print("--------------------------------------", file=sys.stdout)
    
    for i, class_part in enumerate(class_parts):
        if ';' in class_part and '{' not in class_part:  
            print(f"跳过前置声明: class {class_part.split()[0]};")
            continue
        
        class_name = class_part.split()[0]
        if "#ifndef" in class_part and "#define" in class_part:
            include_list = class_part
            continue
        
        classtype = get_classtype_for_class(class_name)
        processed_name = process_class_name(class_name)
        
        new_header_pathr = os.path.abspath(os.path.join(new_dir_name, f"{processed_name}.hpp"))
        new_cpp_pathr = os.path.abspath(os.path.join(new_dir_name, f"{processed_name}.cpp"))
        
        new_header_content = class_part if i == 0 else f'class {class_part}'
        is_main_class = (class_name.lower() == filenameClass) or (processed_name == original_basename)
        
        content_to_write = new_header_content
        if not is_main_class and not content_to_write.endswith("#endif"):
            content_to_write += "\r\n#endif"
        
        with open(new_header_pathr, 'w', encoding=header_encoding) as f:
            if is_main_class:
                f.write(f"{include_list}\r\n")
                f.write(header_includes_str)
                # 主头文件包含其他所有分离出的头文件
                f.write(other_headers_include)
                f.write(content_to_write)
                if final_endif:
                    f.write(final_endif)
            else:
                header_guard = f"swauto_{processed_name.replace('-', '_')}_hpp"
                f.write(f"#ifndef {header_guard}\r\n")
                f.write(f"#define {header_guard}\r\n")
                f.write(header_includes_str) 
                f.write(content_to_write)
        
        split_files.append(new_header_pathr)
        
        new_cpp_content = getclassrep_func(cpp_content, class_name)
        with open(new_cpp_pathr, 'w', encoding=cpp_encoding) as f:
            f.write(f"#include \"{os.path.basename(new_header_pathr)}\"\r\n")
            f.write(filtered_cpp_includes_str)  
            f.write(new_cpp_content)
        
        split_files.append(new_cpp_pathr)
        print(f'生成文件: {new_header_pathr} 和 {new_cpp_pathr} (classtype: {classtype})', file=sys.stdout)
    
    return split_files

def check_codes(rpath):
    with open(rpath, 'rb') as f:
        data = f.read()
        rt = chardet.detect(data)
        return rt['encoding']


# 配置项
# 分离后文件缓存路径(应避免与项目目录相同)
cache_dir = 'D:\\swauto_classsplit_cache'    
# 未匹配到前缀时使用默认为空
DEFAULT_CLASSTYPE = ""
# 前缀映射文件名配置列表 - 可扩展
prefix_mapping = [
    ["SW", "swcore"],
    ["SWA", "swauto"],
    ["FR", "test"],
]

# ############################################## #

# 使用说明:
# 1.安装 Python 与必要的导入类 chardet 
# 2.将本 Python 文件(swsync-partition.py)放置于与你的项目.vcxproj 文件相同的目录下，以确保插件能够正确调用
# 3.代码页面鼠标点击切换至需要分离的头文件页面，使用设定的快捷键激活使用
# 4.本脚本为简化版本，在复杂代码场景下可能无法正确分割类文件。为避免不必要的问题，使用前请做好代码版本控制
# Author: YANGGQ.SW

# 前缀映射具体规则 如 SW 检测需要分离的类名为 SWTest 输出分离后的文件名为 swcore-test.hpp  swcore-test.cpp
# 应确保主体被分离文件中存在的主类名可以被正确映射为被分离文件名，已方便处理，
# 如被分离的头文件为 swauto-test.hpp 那么该头文件内的主体类应该为 SWATest 通过此映射["SWA", "swauto"]可以得到 swauto-test.hpp
# 如有必要时可重构此脚本代码实现更为高级的映射机制与分离机制

# ############################################## #  

if __name__ == '__main__':

    # ################此处不可随意修改################ #

    header_file_path = sys.argv[2].replace("\"", "")    
    split_files = separate_classes(header_file_path)
    for file_path in split_files:
        print(file_path)
    sys.exit(0)
    # ############################################## #
    
