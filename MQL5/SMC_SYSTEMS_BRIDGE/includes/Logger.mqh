//+------------------------------------------------------------------+
//| Logger.mqh — Lightweight file + terminal logger                 |
//+------------------------------------------------------------------+
#property copyright "SMC SYSTEMS"

enum ENUM_LOG_LEVEL
{
   LOG_DEBUG,
   LOG_INFO,
   LOG_WARN,
   LOG_ERROR
};

class CLogger
{
private:
   int         m_handle;
   string      m_path;
   bool        m_verbose;

public:
   void CLogger(void) : m_handle(INVALID_HANDLE), m_verbose(false) {}
   void ~CLogger(void) { Close(); }

   bool Init(string filepath, bool verbose = false)
   {
      m_path = filepath;
      m_verbose = verbose;
      m_handle = FileOpen(m_path, FILE_WRITE|FILE_TXT|FILE_READ|FILE_SHARE_READ, ',');
      if (m_handle == INVALID_HANDLE)
      {
         Print("Logger: Failed to open ", m_path, " error=", GetLastError());
         return false;
      }
      Write(LOG_INFO, "Logger initialized");
      return true;
   }

   void Close(void)
   {
      if (m_handle != INVALID_HANDLE)
      {
         FileClose(m_handle);
         m_handle = INVALID_HANDLE;
      }
   }

   void Write(ENUM_LOG_LEVEL level, string msg)
   {
      string line = StringFormat("[%s] %s", LevelStr(level), msg);
      Print(line);
      if (m_handle != INVALID_HANDLE)
      {
         FileSeek(m_handle, 0, SEEK_END);
         FileWrite(m_handle, TimeToString(TimeCurrent()), level, msg);
         FileFlush(m_handle);
      }
   }

   void Debug(string msg) { if (m_verbose) Write(LOG_DEBUG, msg); }
   void Info(string msg)  { Write(LOG_INFO, msg); }
   void Warn(string msg)  { Write(LOG_WARN, msg); }
   void Error(string msg) { Write(LOG_ERROR, msg); }

private:
   string LevelStr(ENUM_LOG_LEVEL level)
   {
      switch (level)
      {
         case LOG_DEBUG: return "DEBUG";
         case LOG_INFO:  return "INFO";
         case LOG_WARN:  return "WARN";
         case LOG_ERROR: return "ERROR";
      }
      return "UNKNOWN";
   }
};
