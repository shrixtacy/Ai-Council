import os
import re
from pathlib import Path

# Common patterns
# logger.error(f"Something failed: {str(e)}") -> logger.error("Something failed", extra={"error": str(e)})
# logger.info(f"Loaded: {name}") -> logger.info("Loaded", extra={"name": name})

def camel_to_snake(name):
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

def extract_var_name(expr):
    # e.g. str(e) -> error ... optimization.reasoning -> reasoning
    if expr.startswith('str('):
        return "error"
    if expr.startswith('len('):
        return "count"
    
    parts = expr.split('.')
    last_part = parts[-1]
    # strip method calls or math
    last_part = re.sub(r'\(.*?\)', '', last_part)
    last_part = re.sub(r'[:\[].*?$', '', last_part)
    # clean up
    last_part = re.sub(r'[^a-zA-Z0-9_]', '', last_part)
    if not last_part:
        return "value"
    return last_part

def refactor_line(line):
    # Match logger.X(f"...") with optional trailing args like exc_info=True
    # Simplest case: logger.info(f"Message: {var}")
    m = re.search(r'(self\.)?logger\.(debug|info|warning|error|critical|exception)\(f["\'](.*?)(?<!\\)\{([^}]+)\}(.*?)["\'](.*?)\)', line)
    if not m:
        return line, False
    
    prefix = m.group(1) or ""
    level = m.group(2)
    text_before = m.group(3)
    var_expr = m.group(4)
    text_after = m.group(5)
    trailing_args = m.group(6)
    
    var_name = extract_var_name(var_expr)
    
    # clean text
    clean_text = text_before.strip()
    if clean_text.endswith(':'):
        clean_text = clean_text[:-1].strip()
        
    extra_dict = f'{{"{var_name}": {var_expr}}}'
    
    new_call = f'{prefix}logger.{level}("{clean_text}"'
    if trailing_args and trailing_args.strip() != '':
        # Has trailing args
        # Check if it starts with comma
        if trailing_args.startswith(','):
            new_call += f', extra={extra_dict}{trailing_args})'
        else:
            new_call += f', extra={extra_dict}, {trailing_args})'
    else:
        new_call += f', extra={extra_dict})'
        
    new_line = line[:m.start()] + new_call + line[m.end():]
    return new_line, True

def process_directory(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if not file.endswith('.py'):
                continue
            
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            changed = False
            for i, line in enumerate(lines):
                # Apply iteratively for multiple interpolations (hacky handling)
                # For simplicity, if a line has multiple {} we just skip automated and do fallback manual or let it be single
                if line.count('{') > 1 and line.count('}') > 1 and 'f"' in line and 'logger' in line:
                    continue # Skip complex multi-variable interpolations for safety
                
                new_line, modified = refactor_line(line)
                if modified:
                    lines[i] = new_line
                    changed = True
                    
            if changed:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                print(f"Updated {filepath}")

if __name__ == "__main__":
    process_directory("d:/OSCG/yfgf/Ai-Council/ai_council")
