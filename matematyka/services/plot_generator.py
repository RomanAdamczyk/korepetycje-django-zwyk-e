# matematyka/services/plot_generator.py
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.ioff()

import numpy as np
from io import BytesIO
import base64
from sympy import sympify, lambdify, Symbol


def generate_function_plot(
    func_expr: str = None,           # dla zwykłych funkcji (jedna formuła)
    pieces: list = None,             # dla funkcji kawałkami
    x_range: tuple = (-5, 5),
    title: str = None,
    show_grid: bool = True
):
    """
    Draw a function plot based on the provided expression or pieces.
    """
    
    fig, ax = plt.subplots(figsize=(3 , 3), dpi=200)
    
    x_min, x_max = x_range
    x = np.linspace(x_min, x_max, 800)   # więcej punktów = lepsze zaokrąglenia na końcach
    
    if pieces:                           # === FUNKCJA Kawałkami ===
        for piece in pieces:
            expr_str = piece['expr']
            domain = piece.get('domain')          # np. (-4, -2)
            left_closed = piece.get('left_closed', True)
            right_closed = piece.get('right_closed', True)
            
            # Tworzymy maskę
            mask = (x >= domain[0]) & (x <= domain[1])
            
            if not np.any(mask):
                continue
                
            x_sym = Symbol('x')
            expr = sympify(expr_str)
            f = lambdify(x_sym, expr, modules='numpy')
            
            y = f(x)
            y = np.where(mask, y, np.nan)
            
            # Rysujemy linię
            ax.plot(x, y, color='blue', linewidth=2.8)
            
            # Punkty na końcach
            # Lewy koniec
            if left_closed:
                ax.scatter([domain[0]], [f(domain[0])], color='blue', s=80, zorder=5)
            else:
                ax.scatter([domain[0]], [f(domain[0])], color='white', edgecolor='blue', s=80, zorder=5, linewidth=2.5)
            
            # Prawy koniec
            if right_closed:
                ax.scatter([domain[1]], [f(domain[1])], color='blue', s=80, zorder=5)
            else:
                ax.scatter([domain[1]], [f(domain[1])], color='white', edgecolor='blue', s=80, zorder=5, linewidth=2.5)
                
    else:                                # === ZWYKŁA FUNKCJA ===
        if func_expr:
            x_sym = Symbol('x')
            expr = sympify(func_expr)
            f = lambdify(x_sym, expr, modules='numpy')
            y = f(x)
            ax.plot(x, y, color='blue', linewidth=2.8)

    # Ustawienia wykresu
    if title:
        ax.set_title(title, fontsize=15)
    
    ax.set_xlabel("x", fontsize=9, rotation=0)
    ax.set_ylabel("y", fontsize=9, rotation=0)
    
    ax.axhline(0, color='black', linewidth=1.1)
    ax.axvline(0, color='black', linewidth=1.1)

    ax.tick_params(axis='both', which='major', labelsize=6)

    ax.set_xlim(x_min, x_max)
# Zbieramy rzeczywiste wartości y (pomijamy NaN przy funkcjach kawałkami)
    y_values = []
    
    # Dla wszystkich linii na wykresie
    for line in ax.get_lines():
        y_data = line.get_ydata()
        if len(y_data) > 0:
            y_values.append(y_data)
    
    if y_values:
        all_y = np.concatenate(y_values)
        real_y_min = np.nanmin(all_y)
        real_y_max = np.nanmax(all_y)
    else:
        # fallback gdy coś pójdzie nie tak
        real_y_min, real_y_max = -5, 5

    print(f"X: {x_min:.1f} do {x_max:.1f}")
    print(f"Real Y min/max: {real_y_min:.2f} / {real_y_max:.2f}")

    padding = 1.2
    ax.set_ylim(real_y_min - padding, real_y_max + padding)
    ax.set_aspect('equal')
    
    print(f"Final Y range: {real_y_min - padding:.2f} do {real_y_max + padding:.2f}")


    if show_grid:
        x_grid = np.arange(x_min, x_max + 1, 1)
        ax.set_xticks(x_grid)
        y_grid = np.arange(np.floor(real_y_min - padding), np.ceil(real_y_max + padding) + 1, 1)   # <--- ważne!
        ax.set_yticks(y_grid)
        ax.grid(True, linestyle='--', alpha=0.7)

      
    # Zapisywanie
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=200, bbox_inches='tight')
    plt.close(fig)
    
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return f"data:image/png;base64,{image_base64}"