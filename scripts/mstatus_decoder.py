import sys


def decode_mstatus(mstatus):
    fields = {
        "SIE": (1, 1),
        "MIE": (3, 1),
        "SPIE": (5, 1),
        "MPIE": (7, 1),
        "SPP": (8, 1),
        "VS": (9, 2),
        "MPP": (11, 2),
        "FS": (13, 2),
        "XS": (15, 2),
        "MPRV": (17, 1),
        "SUM": (18, 1),
        "MXR": (19, 1),
        "TVM": (20, 1),
        "TW": (21, 1),
        "TSR": (22, 1),
        "UXL": (32, 2),
        "SXL": (34, 2),
        "SBE": (36, 1),
        "MBE": (37, 1),
        "SD": (63, 1),
    }

    decoded_fields = {}
    for field, (pos, size) in fields.items():
        mask = (1 << size) - 1
        decoded_fields[field] = (mstatus >> pos) & mask

    return decoded_fields


def print_decoded_mstatus(decoded_fields):
    for field, value in decoded_fields.items():
        print(f"{field}: {value}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python mstatus_decoder.py <mstatus_value>")
        sys.exit(1)

    mstatus = int(sys.argv[1], 16)
    decoded_fields = decode_mstatus(mstatus)
    print_decoded_mstatus(decoded_fields)
