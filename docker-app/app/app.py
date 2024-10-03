import os
import socket
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dash import Dash, html, dcc, Input, Output, callback
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import pandas as pd
import numpy as np
import psycopg2
import psycopg2.extras as extras
from flask import Flask


def to_array(data):
    data = data.split(",")
    data = np.array(data[1:-1]).astype(float)
    return data


def to_timezone(dtime):
    return dtime.astimezone(ZoneInfo("America/Vancouver"))


def query_esp32(UDP_IP):
    SHARED_UDP_PORT = 4210
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Internet  # UDP
    sock.settimeout(5)
    sock.connect((UDP_IP, SHARED_UDP_PORT))

    print("Querying esp32", flush=True)
    for j in range(30):
        try:
            sock.send("Hello ESP32".encode())
            recv = sock.recv(2**16)
            for i in range(7):
                recv += sock.recv(2**16)
            break
        except TimeoutError:
            time.sleep(5)
            print("Trying again...", flush=True)

    print("Recieved length: ", len(recv), flush=True)
    recv_list = recv.decode("utf-8").split(";")
    date = recv_list[0]
    temps = to_array(recv_list[1])
    hums = to_array(recv_list[2])
    times = to_array(recv_list[3])
    print("Ard times: ", date, times)

    lengths = np.array([temps.shape[0], hums.shape[0], times.shape[0]])
    if (lengths == lengths[0]).all() and (temps.shape[0] > 0):
        sock.send("Received data".encode())

    stop_time = str(date).split(" ")
    stop_datetime = stop_time[1] + " " + stop_time[2]
    datetime_obj = datetime.strptime(stop_datetime, "%Y%m%d %H:%M:%S")

    adjusted_times = times - times[-1]
    print("Adj times: ", adjusted_times, times)
    adjusted_datetimes = [
        datetime_obj + timedelta(seconds=int(diff)) for diff in adjusted_times
    ]
    print("Adj datetimes: ", adjusted_datetimes, flush=True)

    return adjusted_datetimes, temps, hums


def create_plot(adjusted_datetimes, temps, hums):
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(
            x=adjusted_datetimes,
            y=temps,
            mode="lines",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=adjusted_datetimes,
            y=hums,
            mode="lines",
        ),
        secondary_y=True,
    )

    fig.write_html("test.html")


def bulk_insert(table, adjusted_datetimes, temps, hums):
    with open("secrets.txt", "r") as file:
        creds = file.read().rstrip()

    df = {
        "times": adjusted_datetimes,
        "temperature": temps,
        "humidity": hums,
    }
    df = pd.DataFrame(df)  # .iloc[::-1]
    df["times"] = df["times"].dt.tz_localize("utc")
    df["times"] = df["times"].apply(to_timezone)

    try:
        with psycopg2.connect(creds) as conn:
            with conn.cursor() as cur:
                # Create a list of tupples from the dataframe values
                tuples = [tuple(x) for x in df.to_numpy()]
                # Comma-separated dataframe columns
                cols = ",".join(list(df.columns))
                # SQL quert to execute
                query = "INSERT INTO %s(%s) VALUES(%%s,%%s,%%s)" % ("inside", cols)
                try:
                    extras.execute_batch(cur, query, tuples, 100)
                    conn.commit()
                except (Exception, psycopg2.DatabaseError) as error:
                    print("Error: %s" % error)
                    conn.rollback()
                print("execute_batch done")
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)


def select_from(table):
    with open("secrets.txt", "r") as file:
        creds = file.read().rstrip()

    try:
        with psycopg2.connect(creds) as conn:
            with conn.cursor() as cur:
                # execute the CREATE TABLE statement
                cur.execute(f"SELECT * FROM {table}")
                results = pd.DataFrame(cur.fetchall())
                print("results: ", results)
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)


@callback(
    Output("live-update-text", "children"),
    Input("interval-component", "n_intervals"),
)
def update_metrics(n):
    UDP_IP = "10.0.0.83"  # Printed IP from the ESP32 serial monitor
    adjusted_datetimes, temps, hums = query_esp32(UDP_IP)
    bulk_insert("inside", adjusted_datetimes, temps, hums)
    select_from("inside")

    style = {"padding": "5px", "fontSize": "16px", "color": colors["text"]}
    dttz = datetime.now(ZoneInfo("America/Vancouver"))
    print("Adj timez: ", dttz, "\n\n", flush=True)
    return html.Span(f"Last pulled data at: {dttz}", style=style)


server = Flask(__name__)
app = Dash(server=server)

debug = False if os.environ["DASH_DEBUG_MODE"] == "False" else True

colors = {"background": "#111111", "text": "#7FDBFF"}
data = pd.DataFrame(
    {
        "Outside Temperature": [
            21.5,
            21.5,
            21.5,
            21.5,
            21.5,
            21.5,
            21.5,
            21.5,
            21.5,
            21.5,
        ],
        "Inside Temperature": [
            22.5,
            22.5,
            22.5,
            22.5,
            22.5,
            22.5,
            22.5,
            22.5,
            22.5,
            22.5,
        ],
        "Outside Humidity": [60, 60, 60, 60, 60, 60, 60, 60, 60, 60],
        "Inside Humidity": [55, 55, 55, 55, 55, 55, 55, 55, 55, 55],
        "Time": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    }
)

temperature = px.line(
    data, x="Time", y=["Outside Temperature", "Inside Temperature"], markers=True
)
humidity = px.line(
    data, x="Time", y=["Outside Humidity", "Inside Humidity"], markers=True
)

temperature.update_layout(
    plot_bgcolor=colors["background"],
    paper_bgcolor=colors["background"],
    font_color=colors["text"],
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
humidity.update_layout(
    plot_bgcolor=colors["background"],
    paper_bgcolor=colors["background"],
    font_color=colors["text"],
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)

app.layout = html.Div(
    style={"backgroundColor": colors["background"]},
    children=[
        html.H1(
            children=f"Hello Dash in 2022 from {'Dev Server' if debug else 'Prod Server'}",
            style={"textAlign": "center", "color": colors["text"]},
        ),
        html.Div(id="live-update-text"),
        dcc.Graph(id="temperature", figure=temperature),
        dcc.Graph(id="humidity", figure=humidity),
        dcc.Interval(
            id="interval-component",
            interval=300 * 1000,  # in milliseconds
            n_intervals=0,
        ),
    ],
)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port="8050", debug=debug)
