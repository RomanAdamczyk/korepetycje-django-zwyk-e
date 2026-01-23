def split_values_to_map(value_map, variables_list, always_positive_zero=False):
    for var in variables_list:
        if var.split_sign:
            value_str = value_map.get(var.name, '0')
            value = float(value_str)

            if value.is_integer():
                value_map[var.name] = str(int(value))
            else:
                value_map[var.name] = str(value)
            if value < 0:
                znak = '-'
            elif value > 0:
                znak = '+'
            elif always_positive_zero:
                znak = '+'
            else:
                znak = ''

            abs_value = abs(value)
            
            if abs_value.is_integer():
                abs_value_str = str(int(abs_value))
            else:
                abs_value_str = str(abs_value)
            print(f"Variable {var.name}: value={value}, sign={znak}, abs={abs_value_str}")
            value_map[f"{var.name}_sign"] = znak
            value_map[f"{var.name}_abs"] = abs_value_str
    print("Final value_map:", value_map)
    return value_map

def format_value_map(value_map):
    """Float format in value_map, skip _sign/_abs"""

    for k, v in list(value_map.items()):
        if k.endswith('_sign') or k.endswith('_abs'):
            continue
        try:
            value_float = float(v)
            if value_float.is_integer():
                value_map[k] = str(int(value_float))
            else:
                value_map[k] = str(value_float)
        except ValueError:
            value_map[k] = v
    return value_map

