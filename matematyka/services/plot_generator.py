# matematyka/services/plot_generator.py
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.ioff()

import base64
import numpy as np
import json
import re
from io import BytesIO
from sympy import sympify, lambdify, Symbol
from django.template import Template, Context
import logging

logger = logging.getLogger(__name__)


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


    padding = 1.2
    ax.set_ylim(real_y_min - padding, real_y_max + padding)
    ax.set_aspect('equal')
    
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

def prepare_plot_data(pieces, value_map):
    """
    Prepares the pieces of a piecewise function for plotting by substituting variables with their values from the value_map. It also checks for missing variables and raises an error if any are found.
    """

    json_pieces = json.dumps(pieces)
    pattern = r"\{\{(\w+)\}\}"
    values = list(set(re.findall(pattern, json_pieces))) 

    missing = list(set(values) - set(value_map.keys()))

    if missing:
        raise ValueError(f"Missing values for variables: {', '.join(missing)}")
    
    x_min = float(value_map.get('X_MIN'))
    x_max = float(value_map.get('X_MAX'))

    prepared_pieces = []
    for piece in pieces:
        expr = Template(piece['expr']).render(Context(value_map))

        get_domain = piece.get('domain')
        left = get_domain[0] if get_domain else x_min
        right = get_domain[1] if get_domain else x_max

        left_float = float(Template(str(left)).render(Context(value_map)))
        right_float = float(Template(str(right)).render(Context(value_map)))
        domain = [left_float, right_float]

        left_closed = piece.get('left_closed', True)
        right_closed = piece.get('right_closed', True)

        prepared_pieces.append({
            'expr': expr,
            'domain': domain,
            'left_closed': left_closed,
            'right_closed': right_closed
        })

    return {
        "pieces": prepared_pieces,
        "x_min": x_min,
        "x_max": x_max
    }
    
def get_plot_for_task(task, value_map):
    """
    Returns base64 encoded plot for the task or None if no plot is defined.
    """
    if not task.pieces:
        return None
    try:
        parameters = prepare_plot_data(task.pieces, value_map)
        return generate_function_plot(
            pieces=parameters['pieces'],
            x_range=(parameters['x_min'], parameters['x_max']),
        )
    except Exception as e:
        logger.error(f"Error generating plot for task {task.id}: {e}", exc_info=True)
        return None

def prepare_interval_data(intervals, value_map):
    json_intervals = json.dumps(intervals)
    pattern = r"\{\{(\w+)\}\}"
    values = list(set(re.findall(pattern, json_intervals)))

    missing = list(set(values) - set(value_map.keys()))

    if missing:
        raise ValueError(f"Missing values for variables: {', '.join(missing)}")

    x_min = float(value_map.get('X_MIN'))
    x_max = float(value_map.get('X_MAX'))

    prepared_intervals = []
    for interval in intervals:
        get_start = interval.get('start')
        get_end = interval.get('end')

        is_left_infinite = get_start is None or get_start == ''
        is_right_infinite = get_end is None or get_end == ''

        if is_left_infinite:
            left = float(Template(str(x_min)).render(Context(value_map)))
            start = None
        else:
            left = float(Template(str(get_start)).render(Context(value_map)))
            start = left

        if is_right_infinite:
            right = float(Template(str(x_max)).render(Context(value_map)))
            end = None
        else:
            right = float(Template(str(get_end)).render(Context(value_map)))
            end = right

        domain = [left, right]

        left_closed = interval.get('left_closed', True)
        right_closed = interval.get('right_closed', True)

        prepared_intervals.append({
            'domain': domain,
            'left_closed': left_closed,
            'right_closed': right_closed,
            'start': start,
            'end': end
        })

    return {
        "intervals": prepared_intervals,
        "x_min": x_min,
        "x_max": x_max,
    }


def generate_interval_plot(
    intervals: list,
    x_range: tuple = (-5, 5),
    title: str = None,
    show_grid: bool = False
):
    """
    Draw a number-interval plot based on the prepared interval list.
    """
    fig, ax = plt.subplots(figsize=(3, 3), dpi=200)

    x_min, x_max = x_range
    ax.set_xlim(x_min, x_max)
    ax.axhline(0, color='black', linewidth=1.1)

    if title:
        ax.set_title(title, fontsize=15)

    ax.set_xlabel('x', fontsize=9, rotation=0)
    ax.set_ylabel('', fontsize=9, rotation=0)
    ax.set_yticks([])
    ax.get_yaxis().set_visible(False)

    for interval in intervals:
        left_domain, right_domain = interval['domain']

        if right_domain < x_min or left_domain > x_max:
            continue

        left = max(left_domain, x_min)
        right = min(right_domain, x_max)
        if right < left:
            continue

        y = 0.5
        ax.plot([left, right], [y, y], color='blue', linewidth=6, solid_capstyle='butt', zorder=2)
        ax.plot([left, left], [0,y], color='blue', linewidth=2, zorder=2)
        ax.plot([right, right], [0,y], color='blue', linewidth=2, zorder=2)

        if interval['start'] is not None:
            if interval.get('left_closed', True):
                ax.scatter([left], [0], color='blue', s=80, zorder=3)
            else:
                ax.scatter([left], [0], facecolors='white', edgecolors='blue', s=80, zorder=3, linewidths=2)

        if interval['end'] is not None:
            if interval.get('right_closed', True):
                ax.scatter([right], [0], color='blue', s=80, zorder=3)
            else:
                ax.scatter([right], [0], facecolors='white', edgecolors='blue', s=80, zorder=3, linewidths=2)

    if show_grid:
        x_grid = np.arange(x_min, x_max + 1, 1)
        ax.set_xticks(x_grid)
        ax.grid(True, linestyle='--', alpha=0.7)
    else:
        ax.set_xticks(np.arange(x_min, x_max + 1, 1))

    ax.set_ylim(-1, 1)
    ax.set_aspect('auto')

    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=200, bbox_inches='tight')
    plt.close(fig)

    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    return f"data:image/png;base64,{image_base64}"


def get_interval_plot_for_task(task, value_map):
    """
    Returns base64 encoded interval plot for the task or task_group, if intervals exist.
    """
    intervals = []
    if hasattr(task, 'intervals'):
        intervals = [
            {
                'start': interval.start,
                'end': interval.end,
                'left_closed': interval.is_closed_start,
                'right_closed': interval.is_closed_end,
            }
            for interval in task.intervals.all()
        ]

    if not intervals and task.task_group:
        intervals = [
            {
                'start': interval.start,
                'end': interval.end,
                'left_closed': interval.is_closed_start,
                'right_closed': interval.is_closed_end,
            }
            for interval in task.task_group.intervals.all()
        ]

    if not intervals:
        return None

    try:
        parameters = prepare_interval_data(intervals, value_map)
        return generate_interval_plot(
            intervals=parameters['intervals'],
            x_range=(parameters['x_min'], parameters['x_max']),
        )
    except Exception as e:
        logger.error(f"Error generating interval plot for task {task.id}: {e}", exc_info=True)
        return None

