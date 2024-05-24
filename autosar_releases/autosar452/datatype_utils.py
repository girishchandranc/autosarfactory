def get_int_value(text):
    text = text.strip()
    if len(text) > 1 and text[:1] == '0':
        second_char = text[1:2]
        if second_char == 'x' or second_char == 'X':
            # hexa-decimal value
            return int(text[2:], 16)
        elif second_char == 'b' or second_char == 'B':
            # binary value
            return int(text[2:], 2)
        else:
            try:
                # octal value
                return int(text[2:], 8)
            except:
                # return as decimal value if the oct conversion doesn't work in the try
                return int(text)
    else:
        # decimal value
        return int(text)


def get_float_value(text):
    text = text.strip()
    return float(text)


def get_bool_value(text):
    text = text.strip()
    if text == '1' or text.lower() == 'true':
        return True
    else:
        return False


def get_string_value(text):
    return text.strip()
