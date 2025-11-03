import re

import re

def split_commands(cmd_str):
    """Split by commas but ignore commas inside parentheses."""
    res = []
    current = ""
    parens = 0
    for c in cmd_str:
        if c == '(':
            parens += 1
        elif c == ')':
            parens -= 1
        if c == ',' and parens == 0:
            res.append(current)
            current = ""
        else:
            current += c
    if current:
        res.append(current)
    return res

def parse_process(process_str):
    s = process_str.replace(" ", "").replace("\n", "")
    repeat_pattern = re.compile(r'REPEAT\((\w+)\)\{(.*?)\}(?=:|$)')
    repeat_matches = repeat_pattern.findall(s)
    parsed = []

    for repeat_var, inner_content in repeat_matches:
        for_blocks = re.findall(r'FOR_RANGEV\(([^,]+),([^,]+),([^)]+)\)\{(.*?)\}', inner_content)
        for_list = []

        for start_var, end_var, step_var, commands_str in for_blocks:
            commands_raw = split_commands(commands_str)
            commands = []

            for cmd in commands_raw:
                cmatch = re.match(r'(\w+)\((.*)\)', cmd)
                if not cmatch:
                    continue
                cmd_type = cmatch.group(1).upper()
                cmd_param = cmatch.group(2)

                if cmd_type == "MEAN":
                    commands.append({"mean": cmd_param})
                elif cmd_type == "DELAY":
                    commands.append({"delay": cmd_param})
                elif cmd_type == "OUTPUT":
                    outputs = {}
                    pairs = split_commands(cmd_param)
                    for pair in pairs:
                        if '=' in pair:
                            key, val = pair.split('=', 1)
                            outputs[key] = val
                    commands.append({"outputs": outputs})

            for_list.append({
                "start": start_var,
                "end": end_var,
                "step": step_var,
                "commands": commands
            })

        parsed.append({
            "repeats": repeat_var,
            "for_loops": for_list
        })

    return parsed


# --- Test ---
process_str = """REPEAT(C){
    FOR_RANGEV(Vi,Vf,Vr){
        MEAN(R),
        DELAY(D),
        OUTPUT(Vout=V,Iout=I)
    };
    FOR_RANGEV(Vi,Vf,Vr){
        MEAN(R),
        DELAY(D),
        OUTPUT(Vout=V,Iout=I)
    }
    }:
    REPEAT(C){
    FOR_RANGEV(Vi,Vf,Vr){
        MEAN(R),
        DELAY(D),
        OUTPUT(Vout=V,Iout=I)
    };
    FOR_RANGEV(Vi,Vf,Vr){
        MEAN(R),
        DELAY(D),
        OUTPUT(Vout=V,Iout=I)
    }
}"""

import pprint
pprint.pprint(parse_process(process_str))
