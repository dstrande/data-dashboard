import os
from dash import Dash, html, dcc
import plotly.express as px
import pandas as pd

debug = False if os.environ["DASH_DEBUG_MODE"] == "False" else True

colors = {
    'background': '#111111',
    'text': '#7FDBFF'
}

app = Dash(__name__)

server = app.server

data = pd.DataFrame(
    {
        "Outside Temperature": [21.5, 21.5, 21.5, 21.5, 21.5, 21.5, 21.5, 21.5, 21.5, 21.5],
        "Inside Temperature": [22.5, 22.5, 22.5, 22.5, 22.5, 22.5, 22.5, 22.5, 22.5, 22.5],
        "Outside Humidity": [60, 60, 60, 60, 60, 60, 60, 60, 60, 60],
        "Inside Humidity": [55, 55, 55, 55, 55, 55, 55, 55, 55, 55],
        "Time": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    }
)

temperature = px.line(data, x="Time", y=["Outside Temperature", "Inside Temperature"], markers=True)
humidity = px.line(data, x="Time", y=["Outside Humidity", "Inside Humidity"], markers=True)

temperature.update_layout(
    plot_bgcolor=colors['background'],
    paper_bgcolor=colors['background'],
    font_color=colors['text'],
    legend=dict(
    orientation="h",
    yanchor="bottom",
    y=1.02,
    xanchor="right",
    x=1
),
)

humidity.update_layout(
    plot_bgcolor=colors['background'],
    paper_bgcolor=colors['background'],
    font_color=colors['text'],
    legend=dict(
    orientation="h",
    yanchor="bottom",
    y=1.02,
    xanchor="right",
    x=1
),
)

app.layout = html.Div(
    style={'backgroundColor': colors['background']},
    children=[
        html.H1(
            children=f"Hello Dash in 2022 from {'Dev Server' if debug else 'Prod Server'}",
            style={'textAlign': 'center', 'color': colors['text']}),
        html.Div(children="""Dash: A web application framework for your data."""),
        dcc.Graph(id="temperature", figure=temperature),
        dcc.Graph(id="humidity", figure=humidity),
    ],
)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port="8050", debug=debug)
