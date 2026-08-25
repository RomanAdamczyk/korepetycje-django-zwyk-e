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

    raw_x_min = str(value_map.get("X_MIN", "-10"))
    raw_x_max = str(value_map.get("X_MAX", "10"))

    x_min = float(Template(raw_x_min).render(Context(value_map)))
    x_max = float(Template(raw_x_max).render(Context(value_map)))

    prepared_intervals = []
    for interval in intervals:
        get_start = interval.get('start')
        get_end = interval.get('end')

        is_left_infinite = get_start is None or str(get_start).strip() == ''
        is_right_infinite = get_end is None or str(get_end).strip() == ''

        left = x_min if is_left_infinite else float(Template(str(get_start)).render(Context(value_map)))
        right = x_max if is_right_infinite else float(Template(str(get_end)).render(Context(value_map)))

        left_dot = "none" if is_left_infinite else ("closed" if interval.get('left_closed', True) else "open")
        right_dot = "none" if is_right_infinite else ("closed" if interval.get('right_closed', True) else "open")

        prepared_intervals.append({
            'domain': [left, right],
            'left_dot': left_dot,
            'right_dot': right_dot,
            'is_left_infinite': is_left_infinite,
            'is_right_infinite': is_right_infinite
        })

    return {
        'intervals': prepared_intervals,
        'x_min': x_min,
        'x_max': x_max
    }

def generate_interval_plot(
    intervals: list,
    x_range: tuple,
):
    """
    Draw a number-interval plot based on the prepared interval list.
    """
    x_min, x_max = x_range
    fig = px.line()
    y_height = 0.4

    for idx, interval in enumerate(intervals):
        left_domain, right_domain = interval['domain']

        if right_domain < x_min or left_domain > x_max:
            continue

        left_constrained = max(left_domain, x_min)
        right_constrained = min(right_domain, x_max)
        plot_x = []
        plot_y = []
        
        if not interval['is_left_infinite']:
            plot_x.extend([left_constrained, left_constrained])
            plot_y.extend([0, y_height])
        else:
            plot_x.append(left_constrained)
            plot_y.append(y_height)
            
        plot_x.append(right_constrained)
        plot_y.append(y_height)
        
        if not interval['is_right_infinite']:
            plot_x.extend([right_constrained, right_constrained])
            plot_y.extend([y_height, 0])

        # Dodajemy linię przedziału do wykresu
        fig.add_scatter(
            x=plot_x, y=plot_y,
            mode="lines",
            line=dict(width=3, color="#002699"),
            showlegend=False,
            hoverinfo="skip"
        )

        # 2. RYSOWANIE KROPEK NA OSI X (0)
        # Lewa kropka
        if interval['left_dot'] != "none":
            color = "#002699" if interval['left_dot'] == "closed" else "#e5e5e5"
            fig.add_scatter(
                x=[left_constrained],
                y=[0],
                mode="markers",
                marker=dict(size=12, color=color, line=dict(width=2, color="#002699")),
                showlegend=False,
                name="Zamalowane" if interval['left_dot'] == "closed" else "Otwarte"
            )

        # Prawa kropka
        if interval['right_dot'] != "none":
            color = "#002699" if interval['right_dot'] == "closed" else "#e5e5e5"
            fig.add_scatter(
                x=[right_constrained],
                y=[0],
                mode="markers",
                marker=dict(size=12, color=color, line=dict(width=2, color="#002699")),
                showlegend=False,
                name="Zamalowane" if interval['right_dot'] == "closed" else "Otwarte"
            )

    # Matematyczna stylizacja osi liczbowej (wygląd jak linijka)
    fig.update_layout(
        plot_bgcolor="#e5e5e5",
        paper_bgcolor="#e5e5e5",
        height=200,   # Przedział liczbowy jest niski, nie potrzebuje dużo miejsca w pionie
        width=int((x_max - x_min) * 50) + 100, # Elastyczna szerokość zależna od skali
        margin=dict(l=40, r=40, t=20, b=40),
        
        xaxis=dict(
            range=[x_min, x_max],
            gridcolor="#b0b0b0",
            showticklabels=True,
            tickmode="linear",
            dtick=1,
            fixedrange=True,
        ),
        yaxis=dict(
            range=[-0.2, 0.7],     # Sztywne ramy w pionie, by daszek ładnie wyglądał
            showgrid=False,       # Ukrywamy poziome linie siatki, bo są zbędne na osi liczbowej
            showticklabels=False,  # Ukrywamy liczby na osi Y (niepotrzebne w przedziałach)
            fixedrange=True,
            zeroline=True,
            zerolinecolor="black",
            zerolinewidth=2.5,      # Pogrubiona główna oś liczbowa
        )
    )

    return fig.to_html(full_html=False, include_plotlyjs="cdn")

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

