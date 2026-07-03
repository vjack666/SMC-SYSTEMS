//+------------------------------------------------------------------+
//| SignalReceiver.mqh — Poll JSON signal files from Python bridge    |
//+------------------------------------------------------------------+
#property copyright "SMC SYSTEMS"

#include "JSONParser.mqh"
#include "Logger.mqh"

struct SignalData
{
   string   signal_id;
   string   symbol;
   string   action;       // BUY, SELL, CLOSE_BUY, CLOSE_SELL, MODIFY_SLTP
   string   order_type;   // MARKET, LIMIT, STOP
   double   volume;
   double   price;
   double   stop_loss;
   double   take_profit;
   string   comment;
   int      magic_number;
   string   timestamp;
   bool     valid;
};

class CSignalReceiver
{
private:
   string   m_signals_dir;
   CLogger *m_logger;

public:
   void CSignalReceiver(void) : m_logger(NULL) {}

   void Init(string signals_dir, CLogger *logger)
   {
      m_signals_dir = signals_dir;
      m_logger = logger;
   }

   //--- Scan directory for signal_*.json files and return the first unprocessed signal
   SignalData Poll(void)
   {
      SignalData sig;
      sig.valid = false;

      string pattern = m_signals_dir + "\\signal_*.json";
      string filename;
      long search_handle = FileFindFirst(pattern, filename);
      if (search_handle == INVALID_HANDLE)
         return sig;

      while (FileFindNext(search_handle, filename))
      {
         string fullpath = m_signals_dir + "\\" + filename;
         sig = ParseFile(fullpath);
         if (sig.valid)
         {
            // Mark processed: rename to .processed or delete
            // We delete so we don't re-process
            FileDelete(fullpath);
            break;
         }
      }
      FileFindClose(search_handle);
      return sig;
   }

private:
   SignalData ParseFile(string path)
   {
      SignalData sig;
      sig.valid = false;

      string json = CJSONParser::ReadFile(path);
      if (json == "")
      {
        if (m_logger != NULL) m_logger.Warn("SignalReceiver: empty file " + path);
         return sig;
      }

      sig.signal_id   = CJSONParser::GetString(json, "signal_id");
      sig.symbol      = CJSONParser::GetString(json, "symbol");
      sig.action      = CJSONParser::GetString(json, "action");
      sig.order_type  = CJSONParser::GetString(json, "order_type");
      sig.volume      = CJSONParser::GetDouble(json, "volume");
      sig.price       = CJSONParser::GetDouble(json, "price");
      sig.stop_loss   = CJSONParser::GetDouble(json, "stop_loss");
      sig.take_profit = CJSONParser::GetDouble(json, "take_profit");
      sig.comment     = CJSONParser::GetString(json, "comment");
      sig.magic_number= CJSONParser::GetInt(json, "magic_number");
      sig.timestamp   = CJSONParser::GetString(json, "timestamp");

      if (sig.signal_id == "")
      {
         if (m_logger != NULL) m_logger.Warn("SignalReceiver: no signal_id in " + path);
         return sig;
      }
      if (sig.symbol == "")
      {
         if (m_logger != NULL) m_logger.Warn("SignalReceiver: no symbol in " + path);
         return sig;
      }

      sig.valid = true;
      if (m_logger != NULL) m_logger.Info("SignalReceiver: parsed signal " + sig.signal_id + " " + sig.action + " " + sig.symbol);
      return sig;
   }
};
