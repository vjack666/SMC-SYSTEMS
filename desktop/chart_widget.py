from __future__ import annotations

import numpy as np
import pandas as pd
from PySide6.QtCharts import QAreaSeries, QChart, QChartView, QCandlestickSeries, QCandlestickSet, QLineSeries, QDateTimeAxis, QValueAxis
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPen, QPainter
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel

from desktop.crash_log import log_error


class ChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD", "USDCHF", "XAUUSD"])
        top_bar.addWidget(QLabel("Symbol:"))
        top_bar.addWidget(self.symbol_combo)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        self.chart = QChart()
        self.chart.setTitle("SMC Market Chart")
        self.chart.setAnimationOptions(QChart.NoAnimation)
        self.chart.setTheme(QChart.ChartThemeDark)

        self._updating = False
        self._pending_df: pd.DataFrame | None = None

        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        layout.addWidget(self.chart_view)

        self._axis_x: QDateTimeAxis | None = None
        self._axis_y: QValueAxis | None = None
        self._axis_stoch: QValueAxis | None = None

    def connect_worker(self, worker_signals) -> None:
        worker_signals.chart_data_updated.connect(
            self._on_chart_data,
            Qt.ConnectionType.QueuedConnection,
        )

    def _on_chart_data(self, df: pd.DataFrame) -> None:
        if self._updating:
            self._pending_df = df.copy()
            return
        self._updating = True
        try:
            self._render_chart(df)
        except Exception as exc:
            log_error("chart_widget._on_chart_data", exc)
        finally:
            self._updating = False
            if self._pending_df is not None:
                pending = self._pending_df
                self._pending_df = None
                self._on_chart_data(pending)

    def _render_chart(self, df: pd.DataFrame) -> None:
        self.chart.removeAllSeries()
        if self._axis_x:
            self.chart.removeAxis(self._axis_x)
            self._axis_x = None
        if self._axis_y:
            self.chart.removeAxis(self._axis_y)
            self._axis_y = None
        if self._axis_stoch:
            self.chart.removeAxis(self._axis_stoch)
            self._axis_stoch = None

        n_bars = min(len(df), 100)
        data = df.tail(n_bars).reset_index(drop=True)

        candle_series = QCandlestickSeries()
        candle_series.setName("Price")
        candle_series.setIncreasingColor(QColor(0, 200, 83))
        candle_series.setDecreasingColor(QColor(255, 82, 82))

        for _, row in data.iterrows():
            ts = int(pd.Timestamp(row["time"]).timestamp())
            cs = QCandlestickSet(
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
                ts * 1000,
            )
            candle_series.append(cs)

        self.chart.addSeries(candle_series)

        if "ema_fast" in data.columns:
            ema_fast = QLineSeries()
            ema_fast.setName("EMA20")
            ema_fast.setPen(QPen(QColor(100, 181, 246), 1))
            for _, row in data.iterrows():
                ema_fast.append(float(pd.Timestamp(row["time"]).timestamp()) * 1000, float(row["ema_fast"]))
            self.chart.addSeries(ema_fast)

        if "ema_slow" in data.columns:
            ema_slow = QLineSeries()
            ema_slow.setName("EMA50")
            ema_slow.setPen(QPen(QColor(255, 183, 77), 1))
            for _, row in data.iterrows():
                ema_slow.append(float(pd.Timestamp(row["time"]).timestamp()) * 1000, float(row["ema_slow"]))
            self.chart.addSeries(ema_slow)

        if "stoch_k" in data.columns and "stoch_d" in data.columns:
            self._axis_stoch = QValueAxis()
            self._axis_stoch.setRange(0, 100)
            self._axis_stoch.setLabelFormat("%d")
            self._axis_stoch.setTitleText("Stochastic")
            self.chart.addAxis(self._axis_stoch, Qt.AlignRight)

            stoch_k = QLineSeries()
            stoch_k.setName("Stoch %K")
            stoch_k.setPen(QPen(QColor(186, 104, 200), 1))
            for _, row in data.iterrows():
                stoch_k.append(float(pd.Timestamp(row["time"]).timestamp()) * 1000, float(row["stoch_k"]))
            self.chart.addSeries(stoch_k)

            stoch_d = QLineSeries()
            stoch_d.setName("Stoch %D")
            stoch_d.setPen(QPen(QColor(255, 215, 0), 1, Qt.DashLine))
            for _, row in data.iterrows():
                stoch_d.append(float(pd.Timestamp(row["time"]).timestamp()) * 1000, float(row["stoch_d"]))
            self.chart.addSeries(stoch_d)

        if "signal_direction" in data.columns:
            signals = data[data["signal_direction"] != 0]
            for _, row in signals.iterrows():
                marker = QLineSeries()
                dir_ = int(row["signal_direction"])
                price = float(row["close"])
                ts = float(pd.Timestamp(row["time"]).timestamp()) * 1000
                color = QColor(0, 200, 83) if dir_ == 1 else QColor(255, 82, 82)
                marker.setName(f"{'LONG' if dir_ == 1 else 'SHORT'}")
                marker.setPen(QPen(color, 3))
                marker.append(ts - 180000, price)
                marker.append(ts, price + (price * 0.001 if dir_ == 1 else -price * 0.001))
                marker.append(ts + 180000, price)
                self.chart.addSeries(marker)

        self._axis_x = QDateTimeAxis()
        self._axis_x.setFormat("dd HH:mm")
        self._axis_x.setTickCount(10)
        self.chart.addAxis(self._axis_x, Qt.AlignBottom)

        self._axis_y = QValueAxis()
        self._axis_y.setLabelFormat("%.5f")
        self.chart.addAxis(self._axis_y, Qt.AlignLeft)

        for series in self.chart.series():
            series.attachAxis(self._axis_x)
            series.attachAxis(self._axis_y)
            if series.name() in ("Stoch %K", "Stoch %D") and self._axis_stoch:
                series.attachAxis(self._axis_stoch)
