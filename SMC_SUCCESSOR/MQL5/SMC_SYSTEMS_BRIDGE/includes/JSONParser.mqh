//+------------------------------------------------------------------+
//| JSONParser.mqh — Minimal JSON parser for bridge protocol         |
//| Reads JSON files written by Python exporter (flat structure).    |
//+------------------------------------------------------------------+
#property copyright "SMC SYSTEMS"

class CJSONParser
{
public:
   //--- Read the entire file into a single string
   static string ReadFile(string path)
   {
      int h = FileOpen(path, FILE_READ|FILE_TXT|FILE_SHARE_READ, ',');
      if (h == INVALID_HANDLE)
         return "";
      string content = "";
      while (!FileIsEnding(h))
      {
         content += FileReadString(h);
         if (!FileIsEnding(h))
            content += "\n";
      }
      FileClose(h);
      return content;
   }

   //--- Extract a string value for the given key ("key": "value")
   static string GetString(string json, string key)
   {
      string pattern = "\"" + key + "\": \"";
      int start = StringFind(json, pattern);
      if (start < 0) return "";
      start += StringLen(pattern);
      int end = StringFind(json, "\"", start);
      if (end < 0) return "";
      return StringSubstr(json, start, end - start);
   }

   //--- Extract a numeric or boolean value ("key": value)
   static string GetRaw(string json, string key)
   {
      string pattern = "\"" + key + "\": ";
      int start = StringFind(json, pattern);
      if (start < 0) return "";
      start += StringLen(pattern);
      int end = StringFind(json, ",", start);
      if (end < 0) end = StringFind(json, "\n", start);
      if (end < 0) end = StringFind(json, "}", start);
      if (end < 0) end = StringLen(json);
      StringTrimRight(StringSubstr(json, start, end - start));
      return StringSubstr(json, start, end - start);
   }

   static int GetInt(string json, string key)       { return (int)StringToInteger(GetRaw(json, key)); }
   static double GetDouble(string json, string key)  { return StringToDouble(GetRaw(json, key)); }
   static bool GetBool(string json, string key)      { return GetRaw(json, key) == "true"; }
};

//+------------------------------------------------------------------+
//| JSONBuilder.mqh — Minimal JSON writer for result/status files    |
//+------------------------------------------------------------------+
class CJSONBuilder
{
private:
   string m_data;

public:
   void CJSONBuilder(void) { m_data = "{\n"; }

   void AddString(string key, string value)
   {
      m_data += "  \"" + key + "\": \"" + Escape(value) + "\",\n";
   }

   void AddDouble(string key, double value, int digits = 5)
   {
      m_data += "  \"" + key + "\": " + DoubleToString(value, digits) + ",\n";
   }

   void AddInt(string key, int value)
   {
      m_data += "  \"" + key + "\": " + IntegerToString(value) + ",\n";
   }

   void AddBool(string key, bool value)
   {
      m_data += "  \"" + key + "\": " + (value ? "true" : "false") + ",\n";
   }

   string Build(void)
   {
      // Remove trailing comma + newline and close
      int pos = StringFind(m_data, ",\n", StringLen(m_data) - 4);
      if (pos > 0)
         m_data = StringSubstr(m_data, 0, pos + 1) + "\n";
      m_data += "}\n";
      return m_data;
   }

   bool WriteFile(string path)
   {
      string data = Build();
      int h = FileOpen(path, FILE_WRITE|FILE_TXT|FILE_COMMON, ',');
      if (h == INVALID_HANDLE)
         return false;
      FileWrite(h, data);
      FileClose(h);
      return true;
   }

private:
   string Escape(string s)
   {
      StringReplace(s, "\"", "\\\"");
      StringReplace(s, "\n", "\\n");
      return s;
   }
};
