//+------------------------------------------------------------------+
//| OrderManager.mqh — Execute and manage trades on MT5              |
//+------------------------------------------------------------------+
#property copyright "SMC SYSTEMS"

#include "SignalReceiver.mqh"
#include "Logger.mqh"

//--- Result codes (mirrors Python TradeResultCode)
#define TRADE_OK                  0
#define TRADE_REJECTED            1
#define TRADE_TIMEOUT             2
#define TRADE_ERROR               3
#define TRADE_INSUFFICIENT_MARGIN 4
#define TRADE_INVALID_SIGNAL      5
#define TRADE_MARKET_CLOSED       6

struct TradeResultData
{
   string   signal_id;
   int      ticket;
   int      code;
   string   message;
   double   filled_volume;
   double   fill_price;
   double   commission;
   double   swap;
   double   profit;
   string   timestamp;
};

class COrderManager
{
private:
   CLogger *m_logger;
   int      m_magic;

public:
   void COrderManager(void) : m_logger(NULL), m_magic(0) {}

   void Init(int magic, CLogger *logger)
   {
      m_magic = magic;
      m_logger = logger;
   }

   //--- Execute a signal and return the result
   TradeResultData Execute(SignalData &sig)
   {
      TradeResultData res;
      res.signal_id = sig.signal_id;
      res.ticket = 0;
      res.code = TRADE_ERROR;
      res.message = "";
      res.filled_volume = 0;
      res.fill_price = 0;
      res.commission = 0;
      res.swap = 0;
      res.profit = 0;
      res.timestamp = TimeToString(TimeCurrent());

      //--- Validate signal
      if (sig.volume <= 0 && sig.action != "CLOSE_BUY" && sig.action != "CLOSE_SELL" && sig.action != "MODIFY_SLTP")
      {
         res.code = TRADE_INVALID_SIGNAL;
         res.message = "Invalid volume";
         return res;
      }

      //--- Dispatch by action
      if (sig.action == "BUY")
         return ExecuteBuy(sig);
      else if (sig.action == "SELL")
         return ExecuteSell(sig);
      else if (sig.action == "CLOSE_BUY")
         return CloseByType(POSITION_TYPE_BUY);
      else if (sig.action == "CLOSE_SELL")
         return CloseByType(POSITION_TYPE_SELL);
      else if (sig.action == "MODIFY_SLTP")
         return ModifySLTP(sig);
      else
      {
         res.code = TRADE_INVALID_SIGNAL;
         res.message = "Unknown action: " + sig.action;
         return res;
      }
   }

private:
   TradeResultData ExecuteBuy(SignalData &sig)
   {
      TradeResultData res = InitResult(sig.signal_id);

      MqlTradeRequest request;
      MqlTradeResult result;
      ZeroMemory(request);
      ZeroMemory(result);

      request.action   = TRADE_ACTION_DEAL;
      request.symbol   = sig.symbol;
      request.volume   = sig.volume;
      request.type     = ORDER_TYPE_BUY;
      request.price    = SymbolInfoDouble(sig.symbol, SYMBOL_ASK);
      request.sl       = sig.stop_loss;
      request.tp       = sig.take_profit;
      request.deviation= 10;
      request.magic    = m_magic;
      request.comment  = sig.comment;

      if (!OrderSend(request, result))
      {
         res.code = MapError(result.retcode);
         res.message = "OrderSend failed: " + IntegerToString(result.retcode);
         if (m_logger != NULL) m_logger.Error(res.message);
         return res;
      }

      res.ticket = (int)result.order;
      res.code = TRADE_OK;
      res.message = "OK";
      res.filled_volume = result.volume;
      res.fill_price = result.price;
      if (m_logger != NULL) m_logger.Info("BUY executed ticket=" + IntegerToString((int)result.order) + " price=" + DoubleToString(result.price, 5));
      return res;
   }

   TradeResultData ExecuteSell(SignalData &sig)
   {
      TradeResultData res = InitResult(sig.signal_id);

      MqlTradeRequest request;
      MqlTradeResult result;
      ZeroMemory(request);
      ZeroMemory(result);

      request.action   = TRADE_ACTION_DEAL;
      request.symbol   = sig.symbol;
      request.volume   = sig.volume;
      request.type     = ORDER_TYPE_SELL;
      request.price    = SymbolInfoDouble(sig.symbol, SYMBOL_BID);
      request.sl       = sig.stop_loss;
      request.tp       = sig.take_profit;
      request.deviation= 10;
      request.magic    = m_magic;
      request.comment  = sig.comment;

      if (!OrderSend(request, result))
      {
         res.code = MapError(result.retcode);
         res.message = "OrderSend failed: " + IntegerToString(result.retcode);
         if (m_logger != NULL) m_logger.Error(res.message);
         return res;
      }

      res.ticket = (int)result.order;
      res.code = TRADE_OK;
      res.message = "OK";
      res.filled_volume = result.volume;
      res.fill_price = result.price;
      if (m_logger != NULL) m_logger.Info("SELL executed ticket=" + IntegerToString((int)result.order) + " price=" + DoubleToString(result.price, 5));
      return res;
   }

   TradeResultData CloseByType(ENUM_POSITION_TYPE ptype)
   {
      TradeResultData res;
      res.code = TRADE_ERROR;
      res.message = "No position found";

      for (int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if (PositionSelectByTicket(PositionGetTicket(i)))
         {
            if (PositionGetInteger(POSITION_TYPE) == ptype && PositionGetInteger(POSITION_MAGIC) == m_magic)
            {
               MqlTradeRequest request;
               MqlTradeResult result;
               ZeroMemory(request);
               ZeroMemory(result);

               request.action   = TRADE_ACTION_DEAL;
               request.position = PositionGetTicket(i);
               request.symbol   = PositionGetString(POSITION_SYMBOL);
               request.volume   = PositionGetDouble(POSITION_VOLUME);
               request.type     = (ptype == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
               request.price    = (ptype == POSITION_TYPE_BUY)
                                 ? SymbolInfoDouble(request.symbol, SYMBOL_BID)
                                 : SymbolInfoDouble(request.symbol, SYMBOL_ASK);
               request.deviation= 10;
               request.magic    = m_magic;

               if (OrderSend(request, result))
                  {
                     res.code = TRADE_OK;
                     res.message = "Closed";
                     res.ticket = (int)result.order;
                  if (m_logger != NULL) m_logger.Info("Closed position ticket=" + IntegerToString(PositionGetTicket(i)));
               }
               else
               {
                  res.message = "Close failed: " + IntegerToString(result.retcode);
                  if (m_logger != NULL) m_logger.Error(res.message);
               }
               break;
            }
         }
      }
      return res;
   }

   TradeResultData ModifySLTP(SignalData &sig)
   {
      TradeResultData res;
      res.signal_id = sig.signal_id;
      res.code = TRADE_ERROR;
      res.message = "No position found";

      for (int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if (ticket > 0 && PositionSelectByTicket(ticket))
         {
            if (PositionGetString(POSITION_SYMBOL) == sig.symbol && PositionGetInteger(POSITION_MAGIC) == m_magic)
            {
               MqlTradeRequest request;
               MqlTradeResult result;
               ZeroMemory(request);
               ZeroMemory(result);

               request.action   = TRADE_ACTION_SLTP;
               request.position = ticket;
               request.symbol   = sig.symbol;
               request.sl       = sig.stop_loss;
               request.tp       = sig.take_profit;
               request.magic    = m_magic;

               if (OrderSend(request, result))
               {
                  res.code = TRADE_OK;
                  res.message = "SL/TP modified";
                  res.ticket = (int)ticket;
                  if (m_logger != NULL) m_logger.Info("Modified SL/TP for ticket=" + IntegerToString(ticket));
               }
               else
               {
                  res.message = "Modify failed: " + IntegerToString(result.retcode);
                  if (m_logger != NULL) m_logger.Error(res.message);
               }
               break;
            }
         }
      }
      return res;
   }

   TradeResultData InitResult(string signal_id)
   {
      TradeResultData res;
      res.signal_id = signal_id;
      res.ticket = 0;
      res.code = TRADE_ERROR;
      res.message = "";
      res.filled_volume = 0;
      res.fill_price = 0;
      res.commission = 0;
      res.swap = 0;
      res.profit = 0;
      res.timestamp = TimeToString(TimeCurrent());
      return res;
   }

   int MapError(uint retcode)
   {
      switch (retcode)
      {
         case 10004: return TRADE_MARKET_CLOSED;
         case 10006: return TRADE_INSUFFICIENT_MARGIN;
         case 10007: return TRADE_REJECTED;
         case 10008: return TRADE_TIMEOUT;
         case 10014: return TRADE_INVALID_SIGNAL;
         default:    return TRADE_ERROR;
      }
   }
};
