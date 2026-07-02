//+------------------------------------------------------------------+
//| SMC_SYSTEMS_BRIDGE.mq5                                           |
//| Expert Advisor that bridges Python signals to MT5 execution.     |
//| Communicates via JSON files in a shared directory.               |
//+------------------------------------------------------------------+
#property copyright "SMC SYSTEMS"
#property version   "1.00"
#property description "Bridge EA for SMC SYSTEMS — receives signals from Python, executes orders, sends back results."

#include "includes/Logger.mqh"
#include "includes/SignalReceiver.mqh"
#include "includes/OrderManager.mqh"
#include "includes/AccountMonitor.mqh"

//+------------------------------------------------------------------+
//| Input parameters                                                 |
//+------------------------------------------------------------------+
input string   InpSignalsDir   = "signals";           // Signals directory (relative to Terminal_DataDir\Files\)
input int      InpMagicNumber  = 20260701;            // Magic number for order identification
input int      InpHeartbeatSec = 5;                   // Heartbeat interval (seconds)
input bool     InpVerboseLog   = false;               // Enable verbose debug logging
input double   InpDefaultVolume= 0.01;                // Default trade volume if not specified in signal

//+------------------------------------------------------------------+
//| Global objects                                                   |
//+------------------------------------------------------------------+
CLogger          Logger;
CSignalReceiver  SignalReceiver;
COrderManager    OrderManager;
CAccountMonitor  AccountMonitor;

string           g_signals_path;
string           g_results_path;
ulong            g_start_time;
int              g_errors;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit(void)
{
   g_start_time = GetTickCount64();
   g_errors = 0;

   //--- Resolve signal directory
   g_signals_path = TerminalInfoString(TERMINAL_DATA_PATH) + "\\Files\\" + InpSignalsDir;
   g_results_path = g_signals_path;

   //--- Ensure directory exists
   if (!FolderCreate(g_signals_path))
   {
      Print("Failed to create directory: ", g_signals_path, " error=", GetLastError());
      return INIT_FAILED;
   }

   //--- Initialize logger
   string log_path = g_signals_path + "\\bridge_ea.log";
   if (!Logger.Init(log_path, InpVerboseLog))
   {
      Print("Logger init failed, continuing without file logging");
   }
   Logger.Info("SMC_SYSTEMS_BRIDGE v1.00 starting...");

   //--- Initialize components
   SignalReceiver.Init(g_signals_path, &Logger);
   OrderManager.Init(InpMagicNumber, &Logger);
   AccountMonitor.Init(g_signals_path, InpHeartbeatSec, &Logger);

   //--- Set timer for polling (1 second)
   EventSetTimer(1);

   Logger.Info("Bridge EA initialized. Signals dir: " + g_signals_path);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Logger.Info("Bridge EA shutting down. reason=" + IntegerToString(reason));
   Logger.Close();
}

//+------------------------------------------------------------------+
//| Timer function — poll for signals, process, send results         |
//+------------------------------------------------------------------+
void OnTimer(void)
{
   //--- Poll for new signals
   SignalData sig = SignalReceiver.Poll();
   if (sig.valid)
   {
      Logger.Info("Processing signal: " + sig.signal_id + " " + sig.action + " " + sig.symbol);

      //--- Execute the signal
      TradeResultData result = OrderManager.Execute(sig);

      //--- Write result file
      WriteResult(result);
   }

   //--- Send heartbeat and account status
   AccountMonitor.OnTick();
}

//+------------------------------------------------------------------+
//| Write a TradeResult to JSON file readable by Python receiver     |
//+------------------------------------------------------------------+
void WriteResult(TradeResultData &result)
{
   CJSONBuilder json;
   json.AddString("signal_id", result.signal_id);
   json.AddInt("ticket", result.ticket);
   json.AddInt("code", result.code);
   json.AddString("message", result.message);
   json.AddDouble("filled_volume", result.filled_volume);
   json.AddDouble("fill_price", result.fill_price, 5);
   json.AddDouble("commission", result.commission, 2);
   json.AddDouble("swap", result.swap, 2);
   json.AddDouble("profit", result.profit, 2);
   json.AddString("timestamp", result.timestamp);

   string filename = g_results_path + "\\result_" + result.signal_id + ".json";
   bool ok = json.WriteFile(filename);
   if (ok)
      Logger.Info("Result written: " + filename + " code=" + IntegerToString(result.code));
   else
   {
      Logger.Error("Failed to write result: " + filename);
      AccountMonitor.IncrementError();
   }
}
