//+------------------------------------------------------------------+
//| SMC_PS_Bridge.mq5                                                |
//| Polls Common/Files/SMC/ps_levels.csv and applies Entry/SL/TP     |
//| to EarnForex Position Sizer chart lines (ObjectPrefix "PS_").    |
//|                                                                  |
//| DOES NOT open trades. Only moves calculator lines.               |
//|                                                                  |
//| Setup:                                                           |
//|  1) Attach Position Sizer to the chart (same symbol as app).     |
//|  2) Attach this EA on the SAME chart.                            |
//|  3) In Observador: Lab Setup -> "Enviar a Position Sizer".       |
//|  4) Review lot size / risk in Position Sizer; trade only if you  |
//|     press its Trade button yourself.                             |
//+------------------------------------------------------------------+
#property copyright "SMC-SYSTEMS"
#property link      ""
#property version   "1.00"
#property strict
#property description "Loads Entry/SL/TP from Observador into Position Sizer lines. No auto-trade."

input string InpFileName      = "SMC\\ps_levels.csv"; // Handoff file (FILE_COMMON)
input string InpObjectPrefix  = "PS_";                // Must match Position Sizer ObjectPrefix
input int    InpPollMs        = 500;                  // Poll interval (ms)
input bool   InpCreateLines   = true;                 // Create PS lines if missing
input bool   InpAlertOnLoad   = true;                 // Alert when new levels applied
input color  InpEntryColor    = clrDodgerBlue;
input color  InpSLColor       = clrRed;
input color  InpTPColor       = clrLime;

string   g_last_seq = "";
datetime g_last_apply = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   EventSetMillisecondTimer(MathMax(200, InpPollMs));
   Comment("SMC_PS_Bridge: waiting for Observador handoff...\n", InpFileName);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Comment("");
}

//+------------------------------------------------------------------+
void OnTimer()
{
   TryLoadHandoff();
}

//+------------------------------------------------------------------+
void OnTick()
{
   // Keep light; timer does the work.
}

//+------------------------------------------------------------------+
bool TryLoadHandoff()
{
   // Prefer Common Files (cross-terminal); fallback local MQL5/Files.
   int fh = FileOpen(InpFileName, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ);
   if(fh == INVALID_HANDLE)
      fh = FileOpen(InpFileName, FILE_READ | FILE_TXT | FILE_ANSI | FILE_SHARE_READ);
   if(fh == INVALID_HANDLE)
      return false;

   string key, val;
   string seq = "", symbol = "", side = "";
   double entry = 0, sl = 0, tp = 0, risk_pct = 0;
   int auto_trade = 0;
   bool have_entry = false, have_sl = false, have_tp = false;

   while(!FileIsEnding(fh))
   {
      string line = FileReadString(fh);
      if(StringLen(line) < 3)
         continue;
      int comma = StringFind(line, ",");
      if(comma <= 0)
         continue;
      key = StringSubstr(line, 0, comma);
      val = StringSubstr(line, comma + 1);
      StringTrimLeft(key); StringTrimRight(key);
      StringTrimLeft(val); StringTrimRight(val);

      if(key == "seq")            seq = val;
      else if(key == "symbol")    symbol = val;
      else if(key == "side")      side = val;
      else if(key == "entry")   { entry = StringToDouble(val); have_entry = true; }
      else if(key == "sl")      { sl = StringToDouble(val); have_sl = true; }
      else if(key == "tp")      { tp = StringToDouble(val); have_tp = true; }
      else if(key == "risk_pct")  risk_pct = StringToDouble(val);
      else if(key == "auto_trade") auto_trade = (int)StringToInteger(val);
   }
   FileClose(fh);

   if(seq == "" || seq == g_last_seq)
      return false;
   if(!have_entry || !have_sl || !have_tp)
   {
      Print("SMC_PS_Bridge: incomplete levels in ", InpFileName);
      return false;
   }
   if(auto_trade != 0)
   {
      // Hard refuse any future handoff that asks for auto trade.
      Print("SMC_PS_Bridge: refused auto_trade!=0 — bridge is levels-only.");
      g_last_seq = seq;
      return false;
   }

   // Optional symbol check (ignore broker suffix mismatches loosely).
   if(symbol != "" && StringFind(_Symbol, symbol) != 0 && StringFind(symbol, _Symbol) != 0)
   {
      Comment("SMC_PS_Bridge: handoff symbol=", symbol, " chart=", _Symbol,
              " — open matching chart or ignore if suffix differs.");
      // Still apply: many brokers use EURUSD.pro etc.
   }

   if(!ApplyLevels(entry, sl, tp))
   {
      Print("SMC_PS_Bridge: failed to set chart lines");
      return false;
   }

   g_last_seq = seq;
   g_last_apply = TimeLocal();
   string msg = StringFormat(
      "SMC_PS_Bridge LOADED %s %s\nEntry=%.5f  SL=%.5f  TP=%.5f\nRisk%%=%.2f (set in PS UI)\nNO auto-trade — review Position Sizer",
      side, symbol, entry, sl, tp, risk_pct);
   Comment(msg);
   Print(msg);
   if(InpAlertOnLoad)
      Alert("Position Sizer levels loaded from Observador: ", side, " E=", DoubleToString(entry, _Digits));
   ChartRedraw(0);
   return true;
}

//+------------------------------------------------------------------+
bool EnsureHLine(const string name, const double price, const color clr)
{
   if(ObjectFind(0, name) < 0)
   {
      if(!InpCreateLines)
         return false;
      if(!ObjectCreate(0, name, OBJ_HLINE, 0, 0, price))
         return false;
      ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, name, OBJPROP_BACK, false);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, true);
      ObjectSetInteger(0, name, OBJPROP_SELECTED, true);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, false);
   }
   return ObjectSetDouble(0, name, OBJPROP_PRICE, price);
}

//+------------------------------------------------------------------+
bool ApplyLevels(const double entry, const double sl, const double tp)
{
   string e = InpObjectPrefix + "EntryLine";
   string s = InpObjectPrefix + "StopLossLine";
   string t = InpObjectPrefix + "TakeProfitLine";

   bool ok = true;
   ok = EnsureHLine(e, NormalizeDouble(entry, _Digits), InpEntryColor) && ok;
   ok = EnsureHLine(s, NormalizeDouble(sl, _Digits), InpSLColor) && ok;
   ok = EnsureHLine(t, NormalizeDouble(tp, _Digits), InpTPColor) && ok;

   // Nudge Position Sizer to re-read lines on next its timer/tick.
   // Moving selected lines often triggers its recalculation path.
   ObjectSetInteger(0, e, OBJPROP_SELECTED, true);
   ObjectSetInteger(0, s, OBJPROP_SELECTED, true);
   ObjectSetInteger(0, t, OBJPROP_SELECTED, true);
   return ok;
}
//+------------------------------------------------------------------+
