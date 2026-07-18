#property strict

#include <Trade/Trade.mqh>

CTrade trade;

input int PollIntervalSeconds = 1;

string REQUEST_FILE = "python_bridge\\order_request.txt";
string RESULT_FILE = "python_bridge\\order_result.txt";

string TrimValue(string value)
  {
   StringTrimLeft(value);
   StringTrimRight(value);
   return value;
  }

string ReadKey(const string raw, const string key)
  {
   string lines[];
   int count = StringSplit(raw, '\n', lines);
   string prefix = key + "=";

   for(int i = 0; i < count; i++)
     {
      string line = TrimValue(lines[i]);
      if(StringLen(line) == 0)
         continue;
      if(StringFind(line, prefix) == 0)
         return StringSubstr(line, StringLen(prefix));
     }

   return "";
  }

string ReadAllText(const string file_name)
  {
   int handle = FileOpen(file_name, FILE_READ | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if(handle == INVALID_HANDLE)
      return "";

   string content = "";
   while(!FileIsEnding(handle))
      content += FileReadString(handle) + "\n";

   FileClose(handle);
   return content;
  }

bool WriteResult(
   const string request_id,
   const string status,
   const string message,
   const uint retcode,
   const ulong order_ticket,
   const ulong deal_ticket,
   const string symbol,
   const string action,
   const double volume
)
  {
   int handle = FileOpen(RESULT_FILE, FILE_WRITE | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if(handle == INVALID_HANDLE)
      return false;

   FileWriteString(handle, "request_id=" + request_id + "\n");
   FileWriteString(handle, "status=" + status + "\n");
   FileWriteString(handle, "message=" + message + "\n");
   FileWriteString(handle, "retcode=" + IntegerToString((long)retcode) + "\n");
   FileWriteString(handle, "order=" + IntegerToString((long)order_ticket) + "\n");
   FileWriteString(handle, "deal=" + IntegerToString((long)deal_ticket) + "\n");
   FileWriteString(handle, "symbol=" + symbol + "\n");
   FileWriteString(handle, "action=" + action + "\n");
   FileWriteString(handle, "volume=" + DoubleToString(volume, 2) + "\n");

   FileClose(handle);
   return true;
  }

void ProcessRequest()
  {
   if(!FileIsExist(REQUEST_FILE, FILE_COMMON))
      return;

   string raw = ReadAllText(REQUEST_FILE);
   if(StringLen(raw) == 0)
     {
      FileDelete(REQUEST_FILE, FILE_COMMON);
      return;
     }

   string request_id = ReadKey(raw, "request_id");
   string action = ReadKey(raw, "action");
   StringToUpper(action);
   string symbol = ReadKey(raw, "symbol");
   string volume_str = ReadKey(raw, "volume");
   string deviation_str = ReadKey(raw, "deviation");
   string magic_str = ReadKey(raw, "magic");
   string comment = ReadKey(raw, "comment");
   string sl_str = ReadKey(raw, "sl");
   string tp_str = ReadKey(raw, "tp");

   double volume = StringToDouble(volume_str);
   int deviation = (int)StringToInteger(deviation_str);
   long magic = StringToInteger(magic_str);
   double sl = StringLen(sl_str) > 0 ? StringToDouble(sl_str) : 0.0;
   double tp = StringLen(tp_str) > 0 ? StringToDouble(tp_str) : 0.0;

   if(StringLen(request_id) == 0 || StringLen(symbol) == 0 || volume <= 0.0)
     {
      WriteResult(request_id, "error", "Invalid request payload", 0, 0, 0, symbol, action, volume);
      FileDelete(REQUEST_FILE, FILE_COMMON);
      return;
     }

   if(!SymbolSelect(symbol, true))
     {
      WriteResult(request_id, "error", "SymbolSelect failed", 0, 0, 0, symbol, action, volume);
      FileDelete(REQUEST_FILE, FILE_COMMON);
      return;
     }

   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
     {
      WriteResult(request_id, "error", "Terminal trading is disabled", 0, 0, 0, symbol, action, volume);
      FileDelete(REQUEST_FILE, FILE_COMMON);
      return;
     }

   trade.SetTypeFillingBySymbol(symbol);
   trade.SetDeviationInPoints(deviation);
   trade.SetExpertMagicNumber(magic);

   bool ok = false;
   if(action == "BUY")
      ok = trade.Buy(volume, symbol, 0.0, sl, tp, comment);
   else if(action == "SELL")
      ok = trade.Sell(volume, symbol, 0.0, sl, tp, comment);
   else
      WriteResult(request_id, "error", "Unsupported action", 0, 0, 0, symbol, action, volume);

   if(action != "BUY" && action != "SELL")
     {
      FileDelete(REQUEST_FILE, FILE_COMMON);
      return;
     }

   if(ok)
     {
      WriteResult(
         request_id,
         "ok",
         trade.ResultComment(),
         trade.ResultRetcode(),
         trade.ResultOrder(),
         trade.ResultDeal(),
         symbol,
         action,
         volume
      );
     }
   else
     {
      WriteResult(
         request_id,
         "error",
         trade.ResultComment(),
         trade.ResultRetcode(),
         trade.ResultOrder(),
         trade.ResultDeal(),
         symbol,
         action,
         volume
      );
     }

   FileDelete(REQUEST_FILE, FILE_COMMON);
  }

int OnInit()
  {
   EventSetTimer(PollIntervalSeconds);
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
  }

void OnTick()
  {
  }

void OnTimer()
  {
   ProcessRequest();
  }
