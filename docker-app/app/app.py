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
    """Converts the data from string format to an array.

    Removes the first an last characters of the string and converts to float.

    Parameters
    ----------
    data : str
        Partial string from esp32 containing comma separated 1d data.

    Returns
    -------
    data : array
        Data from esp32 now in a 1d array.
    """
    data = data.split(",")
    data = np.array(data[1:-1]).astype(float)
    return data


def to_timezone(dtime):
    """Converts UTC to Vancouver timezone.

    Should account for daylight savings as well.

    Parameters
    ----------
    dtime : datetime
        Datetime in UTC.

    Returns
    -------
    datetime
        Datetime in Vancouver timezone (-7 or -8).
    """
    return dtime.astimezone(ZoneInfo("America/Vancouver"))


def query_esp32(UDP_IP):
    """Queries the specified esp32 logger and returns formatted data.

    Converts time from seconds into datetime using the supplied datetime which
    corresponds to the final measurement. Returns data as 3 arrays.

    Parameters
    ----------
    UDP_IP : str
        The IP of the esp32 temperature logger.

    Returns
    -------
    adjusted_datetimes : array
        Datetime array for each measurement containing timezone information.
    temps : array
        Array of measured temperatures (Celsius).
    hums : array
        Array of measured humidities (%).
    """
    SHARED_UDP_PORT = 4210
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Internet  # UDP
    sock.settimeout(5)
    sock.connect((UDP_IP, SHARED_UDP_PORT))

    print("Querying esp32", flush=True)
    received = False
    while received is False:
        try:
            sock.send("Hello ESP32".encode())
            recv = sock.recv(2**16)
            for i in range(7):
                recv += sock.recv(2**16)
            received = True
        except TimeoutError:
            time.sleep(1)
            print("Trying again...", flush=True)

    print("Recieved length: ", len(recv), flush=True)
    recv_list = recv.decode("utf-8").split(";")
    date = recv_list[0]
    temps = to_array(recv_list[1])
    hums = to_array(recv_list[2])
    times = to_array(recv_list[3])

    lengths = np.array([temps.shape[0], hums.shape[0], times.shape[0]])
    if (lengths == lengths[0]).all() and (temps.shape[0] > 0):
        sock.send("Received data".encode())

    stop_time = str(date).split(" ")
    stop_datetime = stop_time[1] + " " + stop_time[2]
    datetime_obj = datetime.strptime(stop_datetime, "%Y%m%d %H:%M:%S")

    adjusted_times = times - times[-1]
    adjusted_datetimes = [
        datetime_obj + timedelta(seconds=int(diff)) for diff in adjusted_times
    ]

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
    df["times"] = df["times"].dt.tz_localize("utc").apply(to_timezone)

    try:
        with psycopg2.connect(creds) as conn:
            with conn.cursor() as cur:
                # Create a list of tupples from the dataframe values
                tuples = [tuple(x) for x in df.to_numpy()]
                # Comma-separated dataframe columns
                cols = ",".join(list(df.columns))
                # SQL quert to execute
                query = "INSERT INTO %s(%s) VALUES(%%s,%%s,%%s)" % (table, cols)
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
                cur.execute(f"""SELECT * FROM {table}
                            WHERE times > CURRENT_DATE - INTERVAL '14 day';""")
                results = pd.DataFrame(cur.fetchall())
                print("results: ", results)
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)

    return results[1], results[2], results[3]


@callback(
    Output("live-update-text", "children"),
    Input("interval-component", "n_intervals"),
)
def update_metrics(n):
    UDP_IP = "10.0.0.83"  # Printed IP from the ESP32 serial monitor for inside
    adjusted_datetimes, temps, hums = query_esp32(UDP_IP)
    bulk_insert("inside", adjusted_datetimes, temps, hums)

    UDP_IP = "10.0.0.212"  # IP for outside
    adjusted_datetimes, temps, hums = query_esp32(UDP_IP)
    bulk_insert("outside", adjusted_datetimes, temps, hums)

    style = {"padding": "5px", "fontSize": "16px", "color": colors["text"]}
    dttz = datetime.now(ZoneInfo("America/Vancouver"))
    print("Adj timez: ", dttz, "\n\n", flush=True)
    return html.Span(f"Last pulled data at: {dttz}", style=style)


@callback(
    Output("plots", "figure"),
    Input("interval-component", "n_intervals"),
)
def update_data(n):
    datetimes_inside, temps_inside, hums_inside = select_from("inside")
    datetimes_outside, temps_outside, hums_outside = select_from("outside")

    fig = make_subplots(rows=2, cols=1)

    fig.add_trace(
        row=1,
        col=1,
        trace=go.Scatter(
            x=datetimes_inside,
            y=temps_inside,
            name="Inside Temperature",
            mode="lines+markers",
        ),
    )
    fig.add_trace(
        row=1,
        col=1,
        trace=go.Scatter(
            x=datetimes_outside,
            y=temps_outside,
            name="Outside Temperature",
            mode="lines+markers",
        ),
    )
    fig.add_trace(
        row=2,
        col=1,
        trace=go.Scatter(
            x=datetimes_inside,
            y=hums_inside,
            name="Inside Humidity",
            mode="lines+markers",
        ),
    )
    fig.add_trace(
        row=2,
        col=1,
        trace=go.Scatter(
            x=datetimes_outside,
            y=hums_outside,
            name="Outside Humidity",
            mode="lines+markers",
        ),
    )

    fig.update_yaxes(title_text="Temperature (°C)", row=1, col=1)
    fig.update_yaxes(title_text="Humidity (%)", range=[0, 100], row=2, col=1)
    fig.update_xaxes(title_text="Datetime", row=2, col=1)
    fig.update_layout(
        height=1000,
        template="plotly_dark",
        margin=dict(t=10, l=10, b=10, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


server = Flask(__name__)
app = Dash(server=server)

debug = False if os.environ["DASH_DEBUG_MODE"] == "False" else True

colors = {"background": "#111111", "text": "#7FDBFF"}

app.layout = html.Div(
    style={"backgroundColor": colors["background"]},
    children=[
        html.H1(
            children="Indoor/outdoor conditions for the past two weeks",
            style={"textAlign": "center", "color": colors["text"]},
        ),
        html.Div(id="live-update-text"),
        dcc.Graph(id="plots"),
        dcc.Interval(
            id="interval-component",
            interval=3600 * 1000,  # in milliseconds
            n_intervals=0,
        ),
    ],
)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port="8050", debug=debug)
