import socket
import time
from zoneinfo import ZoneInfo
import sys
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras as extras
import pandas as pd
import numpy as np


def to_array(data):
    """Takes data string from esp32 and converts to an array.

    Parameters
    ----------
    data : str
        The raw data string from the esp32.

    Returns
    -------
    data : array
        Data now seperated into an array.
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
        Datetime array for each measurement without timezone information.
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


def bulk_insert(table, adjusted_datetimes, temps, hums):
    """Inserts data in the postgreSQL server.

    Additionally, uses the to_timezone function to convert the datetime to
    datetime with timezone.

    Parameters
    ----------
    table : str
        The name of the table to insert the data into.
    adjusted_datetimes : array
        Datetime array for each measurement without timezone information.
    temps : array
        Array of measured temperatures (Celsius).
    hums : array
        Array of measured humidities (%).
    """
    with open("secrets.txt", "r") as file:
        creds = file.read().rstrip()

    df = {
        "times": adjusted_datetimes,
        "temperature": temps,
        "humidity": hums,
    }
    df = pd.DataFrame(df)
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


if __name__ == "__main__":
    adjusted_datetimes, temps, hums = query_esp32(sys.argv[1])
    bulk_insert(sys.argv[2], adjusted_datetimes, temps, hums)
