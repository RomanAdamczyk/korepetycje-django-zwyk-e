# matematyka/services/plot_generator.py

import matplotlib.pyplot as plt
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
    Rysuje wykres funkcji - zarówno zwykłej jak i kawałkami.
    """
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
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
    
    ax.set_xlabel("x", fontsize=12)
    ax.set_ylabel("y", fontsize=12)
    
    if show_grid:
        ax.grid(True, linestyle='--', alpha=0.7)
    
    ax.axhline(0, color='black', linewidth=1.1)
    ax.axvline(0, color='black', linewidth=1.1)
    
    ax.set_xlim(x_min, x_max)
    y_min, y_max = ax.get_ylim()
    ax.set_ylim(y_min - 0.5, y_max + 0.5)

    # Zapisywanie
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=200, bbox_inches='tight')
    plt.close(fig)
    
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return f"data:image/png;base64,{image_base64}"