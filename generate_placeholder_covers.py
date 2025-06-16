import os

WIDTH = 512
HEIGHT = 512
BACKGROUND = (240, 240, 240)
DIGIT_COLOR = (0, 0, 0)
SCALE = 20

DIGITS = {
    '0': [
        '01110',
        '10001',
        '10011',
        '10101',
        '11001',
        '10001',
        '01110',
    ],
    '1': [
        '00100',
        '01100',
        '00100',
        '00100',
        '00100',
        '00100',
        '01110',
    ],
    '2': [
        '01110',
        '10001',
        '00001',
        '00110',
        '01000',
        '10000',
        '11111',
    ],
    '3': [
        '11110',
        '00001',
        '00001',
        '01110',
        '00001',
        '00001',
        '11110',
    ],
    '4': [
        '00010',
        '00110',
        '01010',
        '10010',
        '11111',
        '00010',
        '00010',
    ],
    '5': [
        '11111',
        '10000',
        '11110',
        '00001',
        '00001',
        '10001',
        '01110',
    ],
    '6': [
        '00110',
        '01000',
        '10000',
        '11110',
        '10001',
        '10001',
        '01110',
    ],
    '7': [
        '11111',
        '00001',
        '00010',
        '00100',
        '01000',
        '01000',
        '01000',
    ],
    '8': [
        '01110',
        '10001',
        '10001',
        '01110',
        '10001',
        '10001',
        '01110',
    ],
    '9': [
        '01110',
        '10001',
        '10001',
        '01111',
        '00001',
        '00010',
        '01100',
    ],
}

def draw_digit(canvas, digit, x, y, scale=SCALE):
    pattern = DIGITS[digit]
    for row_idx, row in enumerate(pattern):
        for col_idx, ch in enumerate(row):
            if ch == '1':
                for dy in range(scale):
                    for dx in range(scale):
                        px = x + col_idx*scale + dx
                        py = y + row_idx*scale + dy
                        if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                            index = 3*(py*WIDTH + px)
                            canvas[index:index+3] = bytes(DIGIT_COLOR)

def create_image(text, filename):
    canvas = bytearray(BACKGROUND*WIDTH*HEIGHT)

    digit_width = len(DIGITS['0'][0])*SCALE
    digit_height = len(DIGITS['0'])*SCALE
    spacing = SCALE
    total_width = len(text)*digit_width + (len(text)-1)*spacing
    start_x = max((WIDTH - total_width)//2, 0)
    start_y = max((HEIGHT - digit_height)//2, 0)

    x = start_x
    for ch in text:
        draw_digit(canvas, ch, x, start_y)
        x += digit_width + spacing

    with open(filename, 'wb') as f:
        f.write(f"P6\n{WIDTH} {HEIGHT}\n255\n".encode())
        f.write(canvas)

def main():
    os.makedirs('cover_images', exist_ok=True)
    days = ['1', '3', '5', '7', '14', '30']
    for day in days:
        create_image(day, f'cover_images/day_{day}.ppm')

if __name__ == '__main__':
    main()
