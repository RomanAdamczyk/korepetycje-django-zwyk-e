# matematyka/services/plot_generator.py
import matplotlib

from matematyka.models import AnswerOption, Task
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.ioff()

import base64
import numpy as np
import plotly.express as px
import json
import re
from io import BytesIO
from sympy import sympify, lambdify, Symbol
from django.template import Template, Context
import logging

logger = logging.getLogger(__name__)


def generate_function_plot(
            prepared_pieces: list, x_range: tuple
) -> str:

    """
    Draw a function plot based on the provided expression or pieces.
    """

    x_min, x_max = x_range
    x_grid = np.linspace(x_min, x_max, 600)

    all_x, all_y, all_groups = [], [], []
    scatter_x, scatter_y, scatter_modes = [], [], []

    for idx, piece in enumerate(prepared_pieces):
        f = piece["expr"]
        left, right = piece["domain"]

        mask = (x_grid >= left) & (x_grid <= right)
        x_visible = x_grid[mask]
        if len(x_visible) == 0:
            continue

        y_visible = f(x_visible)

        for xv, yv in zip(x_visible, y_visible):
            all_x.append(xv)
            all_y.append(yv)
            all_groups.append(f"Scrap {idx+1}")

        left_dot_type = piece["left_dot"]
        right_dot_type = piece["right_dot"]

        if left_dot_type != "none":
            scatter_x.append(left)
            scatter_y.append(f(left))
            scatter_modes.append(
                "Closed" if left_dot_type == "closed" else "Open"
            )

        if right_dot_type != "none":
            scatter_x.append(right)
            scatter_y.append(f(right))
            scatter_modes.append(
                "Closed" if right_dot_type == "closed" else "Open"
            )

    fig = px.line(
        x=all_x,
        y=all_y,
        color=all_groups,
        labels={"x": "Oś X", "y": "Oś Y"},
    )

    for sx, sy, smode in zip(scatter_x, scatter_y, scatter_modes):
        color = "#002699" if smode == "Zamalowane" else "white"
        fig.add_scatter(
            x=[sx],
            y=[sy],
            mode="markers",
            marker=dict(
                size=10, color=color, line=dict(width=2, color="#002699")
            ),
            showlegend=False,
            # hoverinfo="skip",  # UNNOTICATE THIS LINE IF YOU WANT TO TURN OFF COORDINATE VIEWING
        )

    if all_y:
        y_min, y_max = np.min(all_y), np.max(all_y)
        padding = (y_max - y_min) * 0.1 if y_max != y_min else 2
        y_range = [min(y_min - padding, -1), y_max + padding]
    else:
        y_range = [-5, 5]
    
    x_span = x_max - x_min 
    y_span = y_range[1] - y_range[0]  

    pixel_per_unit = 60
    chart_width = int(x_span * pixel_per_unit) + 150  
    chart_height = int(y_span * pixel_per_unit) + 100 

    fig.update_layout(
        plot_bgcolor="#e5e5e5",
        paper_bgcolor="#e5e5e5",
        
        # === SZTYWNY ROZMIAR CAŁEGO OKNA (Zwęża i dopasowuje rysunek) ===
        width=chart_width,
        height=chart_height,
        margin=dict(l=50, r=30, t=30, b=50),  # Minimalne marginesy boczne
        
        xaxis=dict(
            range=[x_min, x_max],
            gridcolor="#b0b0b0",
            zeroline=True,
            zerolinecolor="black",
            zerolinewidth=1.5,
            showticklabels=True,
            tickmode="linear",
            dtick=1,
            anchor="y",
            side="bottom",
            constrain="domain",
            fixedrange=True,
            position=0,
        ),
        yaxis=dict(
            range=y_range,
            gridcolor="#b0b0b0",
            zeroline=True,
            zerolinecolor="black",
            zerolinewidth=1.5,
            scaleanchor="x",
            scaleratio=1,
            showticklabels=True,
            tickmode="linear",
            dtick=1,               
            anchor="x",
            side="left",
            fixedrange=True,
            position=0,
        ),
        showlegend=False,
    )

    return fig.to_html(full_html=False, include_plotlyjs="cdn")

def prepare_plot_data(pieces: list, value_map: dict) -> list:
    """
    Prepares the pieces of a piecewise function for plotting by substituting variables with their values from the value_map. It also checks for missing variables and raises an error if any are found.
    """

    json_pieces = json.dumps(pieces)
    pattern = r"\{\{(\w+)\}\}"
    values = list(set(re.findall(pattern, json_pieces))) 
    missing = list(set(values) - set(value_map.keys()))
    if missing:
        raise ValueError(f"Brak wartości dla zmiennych: {', '.join(missing)}")    

    raw_x_min = str(value_map.get("X_MIN", "-10"))
    raw_x_max = str(value_map.get("X_MAX", "10"))

    x_min = float(Template(raw_x_min).render(Context(value_map)))
    x_max = float(Template(raw_x_max).render(Context(value_map)))

    # x_min = float(rendered_x_min)
    # x_max = float(rendered_x_max)

    prepared_pieces = []
    for piece in pieces:
        expr = Template(piece['expr']).render(Context(value_map))

        safe_dict = {
            "x": None,
            "np": np,
            "sin": np.sin,
            "cos": np.cos,
            "sqrt": np.sqrt,
            "abs": np.abs,
        }
        func_obj = eval(f"lambda x: {expr}", {"__builtins__": None}, safe_dict)

        get_domain = piece.get('domain')
        left = (
            float(Template(str(get_domain[0])).render(Context(value_map)))
            if get_domain
            else x_min
        )
        right = (
            float(Template(str(get_domain[1])).render(Context(value_map)))
            if get_domain
            else x_max
        )

        prepared_pieces.append(
            {
                "expr": func_obj,
                "domain": [left, right],
                "left_dot": piece.get("left_dot", "none"),
                "right_dot": piece.get("right_dot", "none"),
            }
        )

    return prepared_pieces, x_min, x_max

def get_plot_for_task(obj, value_map):
    """
    Returns interactive Plotly HTML string for the task or task group,
    or None if no plot is defined. Works with both Task and TaskGroup models.
    """
    if not obj.pieces:
        return None
    try:
        # x_min_val = float(obj.x_min) if obj.x_min is not None else -6.0
        # x_max_val = float(obj.x_max) if obj.x_max is not None else 6.0

        # value_map["X_MIN"] = x_min_val
        # value_map["X_MAX"] = x_max_val
        clean_pieces, x_min, x_max = prepare_plot_data(obj.pieces, value_map)

        return generate_function_plot(
            prepared_pieces=clean_pieces,
            x_range=(x_min, x_max),
        )
    except Exception as e:
        logger.error(f"Error generating plot for object {obj.id}: {e}", exc_info=True)
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
    fig, ax = plt.subplots(figsize=(3, 1), dpi=200)

    x_min, x_max = x_range
    ax.set_xlim(x_min, x_max)

    ax.spines['bottom'].set_position(('data', 0))
    ax.spines['top'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['right'].set_visible(False)

    ax.xaxis.set_ticks_position('bottom')
    ax.xaxis.set_label_position('bottom')

    ax.axhline(0, color='black', linewidth=1.1)

    if title:
        ax.set_title(title, fontsize=15)

    ax.set_xlabel('x', fontsize=9, rotation=0)
    ax.set_ylabel('', fontsize=9, rotation=0)
    ax.set_yticks([])
    ax.get_yaxis().set_visible(False)
    ax.tick_params(axis='x', which='major', pad=2, labelsize=8)

    fig.tight_layout()

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

        if interval['start'] is not None:
            ax.plot([left, left], [0,y], color='blue', linewidth=2, zorder=2)            
            if interval.get('left_closed', True):
                ax.scatter([left], [0], color='blue', s=80, zorder=3)
            else:
                ax.scatter([left], [0],  edgecolors='blue', s=80, zorder=3, linewidths=2)

        if interval['end'] is not None:
            ax.plot([right, right], [0,y], color='blue', linewidth=2, zorder=2)
            if interval.get('right_closed', True):
                ax.scatter([right], [0], color='blue', s=80, zorder=3)
            else:
                ax.scatter([right], [0],  edgecolors='blue', s=80, zorder=3, linewidths=2)

    if show_grid:
        x_grid = np.arange(x_min, x_max + 1, 1)
        ax.set_xticks(x_grid)
        ax.grid(True, linestyle='--', alpha=1)
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


def get_interval_plot_for_task(source, value_map):
    """
    Returns base64 encoded interval plot for the task or task_group, if intervals exist.
    """
    intervals = []
    if isinstance(source, AnswerOption):
        for link in source.answer_option_intervals.all():
            interval = link.interval
            intervals.append({
                'start': interval.start,
                'end': interval.end,
                'left_closed': interval.is_closed_start,
                'right_closed': interval.is_closed_end,
            })
    elif isinstance(source, Task):
        if hasattr(source, 'intervals'):
            intervals = [
                {
                    'start': interval.start,
                    'end': interval.end,
                    'left_closed': interval.is_closed_start,
                    'right_closed': interval.is_closed_end,
                }
                for interval in source.intervals.all()
            ]

        if not intervals and source.task_group:
            intervals = [
                {
                    'start': interval.start,
                    'end': interval.end,
                    'left_closed': interval.is_closed_start,
                    'right_closed': interval.is_closed_end,
                }
                for interval in source.task_group.intervals.all()
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
        logger.error(f"Error generating interval plot for task {source.id}: {e}", exc_info=True)
        return None

