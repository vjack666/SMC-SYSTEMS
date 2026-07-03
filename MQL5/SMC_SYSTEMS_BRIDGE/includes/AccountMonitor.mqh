//+------------------------------------------------------------------+
//| AccountMonitor.mqh — Periodically send account status to bridge   |
//+------------------------------------------------------------------+
#property copyright "SMC SYSTEMS"

#include "JSONParser.mqh"
#include "Logger.mqh"

class CAccountMonitor
{
private:
   string   m_status_dir;
   int      m_heartbeat_interval;  // seconds
   datetime m_last_heartbeat;
   datetime m_last_status;
   int      m_errors_window;
   CLogger *m_logger;

public:
   void CAccountMonitor(void) : m_heartbeat_interval(5), m_last_heartbeat(0), m_last_status(0), m_errors_window(0), m_logger(NULL) {}

   void Init(string status_dir, int heartbeat_sec, CLogger *logger)
   {
      m_status_dir = status_dir;
      m_heartbeat_interval = heartbeat_sec;
      m_logger = logger;
      m_last_heartbeat = 0;
      m_last_status = 0;
      m_errors_window = 0;
   }

   void OnTick(void)
   {
      datetime now = TimeCurrent();

      //--- Send heartbeat every N seconds
      if (now - m_last_heartbeat >= m_heartbeat_interval)
      {
         SendHeartbeat();
         m_last_heartbeat = now;
      }

      //--- Send full status every 60 seconds
      if (now - m_last_status >= 60)
      {
         SendAccountStatus();
         m_last_status = now;
      }
   }

   void IncrementError(void)
   {
      m_errors_window++;
   }

   void ResetErrors(void)
   {
      m_errors_window = 0;
   }

private:
   void SendHeartbeat(void)
   {
      CJSONBuilder json;
      json.AddString("source", "mt5");
      json.AddString("status", "ALIVE");
      json.AddDouble("uptime_sec", (double)GetTickCount64() / 1000.0, 1);
      json.AddInt("errors_last_window", m_errors_window);
      json.AddString("timestamp", TimeToString(TimeCurrent()));

      string path = m_status_dir + "\\heartbeat_mt5.json";
      bool ok = json.WriteFile(path);
      if (m_logger != NULL)
      {
         if (ok)
            m_logger.Debug("Heartbeat written to " + path);
         else
            m_logger.Warn("Failed to write heartbeat to " + path);
      }
   }

   void SendAccountStatus(void)
   {
      if (!AccountInfoInteger(ACCOUNT_LOGIN))
      {
         if (m_logger != NULL) m_logger.Error("AccountMonitor: no account selected");
         return;
      }

      double balance  = AccountInfoDouble(ACCOUNT_BALANCE);
      double equity   = AccountInfoDouble(ACCOUNT_EQUITY);
      double margin   = AccountInfoDouble(ACCOUNT_MARGIN);
      double free     = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
      double margin_lvl = (margin > 0) ? (equity / margin * 100.0) : 0;
      double floating = equity - balance;
      int open_pos    = PositionsTotal();

      CJSONBuilder json;
      json.AddInt("account_id", (int)AccountInfoInteger(ACCOUNT_LOGIN));
      json.AddDouble("balance", balance, 2);
      json.AddDouble("equity", equity, 2);
      json.AddDouble("margin", margin, 2);
      json.AddDouble("margin_free", free, 2);
      json.AddDouble("margin_level", margin_lvl, 2);
      json.AddDouble("floating_pnl", floating, 2);
      json.AddInt("open_positions", open_pos);
      json.AddString("server_time", TimeToString(TimeCurrent()));
      json.AddString("timestamp", TimeToString(TimeCurrent()));

      string path = m_status_dir + "\\account_status.json";
      bool ok = json.WriteFile(path);
      if (m_logger != NULL)
      {
         if (ok)
            m_logger.Info("Account status sent: balance=" + DoubleToString(balance, 2) + " equity=" + DoubleToString(equity, 2));
         else
            m_logger.Warn("Failed to write account status to " + path);
      }
   }
};
