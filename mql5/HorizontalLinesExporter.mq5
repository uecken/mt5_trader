//+------------------------------------------------------------------+
//|                                     HorizontalLinesExporter.mq5  |
//|                          水平線自動エクスポート Indicator         |
//|           チャートに常駐し、水平線変更時に自動でJSONを更新        |
//+------------------------------------------------------------------+
#property copyright "MT5 Trader System"
#property version   "1.00"
#property indicator_chart_window
#property indicator_plots 0  // 描画なし（エクスポート専用）

//--- Input parameters
input string OutputFileName = "horizontal_lines.json";  // 出力ファイル名
input int    UpdateInterval = 1;                        // 更新間隔（秒）

//--- Global variables
datetime lastExportTime = 0;
int      lastLineCount = -1;

//+------------------------------------------------------------------+
//| Indicator initialization function                                 |
//+------------------------------------------------------------------+
int OnInit()
{
    // タイマー設定（定期更新用）
    EventSetTimer(UpdateInterval);

    // 初回エクスポート
    ExportToJSON();

    Print("HorizontalLinesExporter initialized. Output: ", OutputFileName);
    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Indicator deinitialization function                               |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    EventKillTimer();
    Print("HorizontalLinesExporter stopped");
}

//+------------------------------------------------------------------+
//| Main calculation function (required for indicator)                |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
{
    return(rates_total);
}

//+------------------------------------------------------------------+
//| Chart event handler - detects object changes                      |
//+------------------------------------------------------------------+
void OnChartEvent(const int id,
                  const long &lparam,
                  const double &dparam,
                  const string &sparam)
{
    // オブジェクト関連イベントを検知
    switch(id)
    {
        case CHARTEVENT_OBJECT_CREATE:
            Print("Object created: ", sparam);
            ExportToJSON();
            break;

        case CHARTEVENT_OBJECT_DELETE:
            Print("Object deleted: ", sparam);
            ExportToJSON();
            break;

        case CHARTEVENT_OBJECT_DRAG:
            Print("Object moved: ", sparam);
            ExportToJSON();
            break;

        case CHARTEVENT_OBJECT_CHANGE:
            Print("Object changed: ", sparam);
            ExportToJSON();
            break;
    }
}

//+------------------------------------------------------------------+
//| Timer event handler - periodic export                             |
//+------------------------------------------------------------------+
void OnTimer()
{
    // 念のため定期的にもエクスポート
    ExportToJSON();
}

//+------------------------------------------------------------------+
//| Export horizontal lines to JSON file                              |
//| Scans ALL open charts with the same symbol                        |
//+------------------------------------------------------------------+
void ExportToJSON()
{
    string currentSymbol = Symbol();

    // JSON構築
    string json = "{\n";
    json += "  \"symbol\": \"" + currentSymbol + "\",\n";
    json += "  \"timestamp\": \"" + TimeToString(TimeCurrent(), TIME_DATE|TIME_MINUTES|TIME_SECONDS) + "\",\n";
    json += "  \"lines\": [\n";

    bool first = true;
    int lineCount = 0;

    // すべての開いているチャートをスキャン
    long chartId = ChartFirst();
    while(chartId >= 0)
    {
        // 同じ銘柄のチャートから水平線を収集
        string chartSymbol = ChartSymbol(chartId);
        if(chartSymbol == currentSymbol)
        {
            int total = ObjectsTotal(chartId, 0, OBJ_HLINE);

            for(int i = 0; i < total; i++)
            {
                string name = ObjectName(chartId, i, 0, OBJ_HLINE);
                if(name == "") continue;

                // ChartExporterEAがコピーした水平線は除外
                if(StringFind(name, "_copied_") >= 0) continue;

                double price = ObjectGetDouble(chartId, name, OBJPROP_PRICE);
                color clr = (color)ObjectGetInteger(chartId, name, OBJPROP_COLOR);
                string colorHex = ColorToHex(clr);

                if(!first) json += ",\n";
                first = false;

                // チャートIDを名前に含めてユニークにする
                string uniqueName = name + "_" + IntegerToString(chartId);

                json += "    {\n";
                json += "      \"name\": \"" + uniqueName + "\",\n";
                json += "      \"price\": " + DoubleToString(price, 2) + ",\n";
                json += "      \"color\": \"" + colorHex + "\"\n";
                json += "    }";

                lineCount++;
            }
        }

        chartId = ChartNext(chartId);
    }

    json += "\n  ]\n";
    json += "}\n";

    // ファイルに書き込み（FILE_COMMONでMT5共通フォルダに保存）
    int handle = FileOpen(OutputFileName, FILE_WRITE|FILE_TXT|FILE_COMMON);
    if(handle != INVALID_HANDLE)
    {
        FileWriteString(handle, json);
        FileClose(handle);

        // ライン数が変わった場合のみログ出力
        if(lineCount != lastLineCount)
        {
            Print("Exported ", lineCount, " horizontal lines from all charts");
            lastLineCount = lineCount;
        }
    }
    else
    {
        Print("File write error: ", GetLastError());
    }

    lastExportTime = TimeCurrent();
}

//+------------------------------------------------------------------+
//| Convert color to hex string                                       |
//+------------------------------------------------------------------+
string ColorToHex(color clr)
{
    // MQL5のcolorはBGR形式なのでRGBに変換
    int r = (clr & 0x0000FF);
    int g = (clr & 0x00FF00) >> 8;
    int b = (clr & 0xFF0000) >> 16;

    return StringFormat("#%02X%02X%02X", r, g, b);
}
//+------------------------------------------------------------------+
