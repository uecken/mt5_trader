//+------------------------------------------------------------------+
//|                                              ChartExporter.mq5   |
//|                       チャートスクリーンショット自動エクスポート    |
//|       Pythonからのリクエストを検知してChartScreenShot()を実行     |
//|       全時間足(D1, H4, M15, M5, M1)を自動キャプチャ               |
//+------------------------------------------------------------------+
//| ※重要: このインジケータ版ではChartOpen()が使用できません（Error 4105）|
//|   代わりに ChartExporterEA.mq5 (EA版) を使用してください。        |
//|   EAとしてチャートにアタッチすることで、新しいチャートを開いて     |
//|   スクリーンショットを取得できます。                              |
//+------------------------------------------------------------------+
#property copyright "MT5 Trader System"
#property version   "2.00"
#property indicator_chart_window
#property indicator_plots 0  // 描画なし（エクスポート専用）

//--- Input parameters
input int    CheckInterval = 1;           // リクエストチェック間隔（秒）
input int    ImageWidth = 1920;           // 画像幅
input int    ImageHeight = 1080;          // 画像高さ
input string RequestFile = "screenshot_request.txt";  // リクエストファイル名
input string OutputPrefix = "chart_";     // 出力ファイル名プレフィックス
input int    ChartLoadWait = 500;         // チャート読み込み待機（ミリ秒）

//--- Timeframe configuration for multi-timeframe capture
string TIMEFRAME_NAMES_TO_CAPTURE[] = {"D1", "H4", "M15", "M5", "M1"};
ENUM_TIMEFRAMES TIMEFRAMES_TO_CAPTURE[] = {PERIOD_D1, PERIOD_H4, PERIOD_M15, PERIOD_M5, PERIOD_M1};

//--- Chart IDs for opened charts (to track which ones we opened)
long openedChartIds[];

//--- Source chart ID (the chart where this indicator is attached)
long sourceChartId;

//+------------------------------------------------------------------+
//| Indicator initialization function                                 |
//+------------------------------------------------------------------+
int OnInit()
{
    sourceChartId = ChartID();  // このインジケータがアタッチされているチャートのID
    EventSetTimer(CheckInterval);
    Print("ChartExporter initialized. Waiting for requests...");
    Print("Request file: ", RequestFile);
    Print("Source chart ID: ", sourceChartId);
    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Indicator deinitialization function                               |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    EventKillTimer();
    Print("ChartExporter stopped");
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
//| Timer event handler - check for screenshot requests               |
//+------------------------------------------------------------------+
void OnTimer()
{
    // リクエストファイルの存在チェック
    if(FileIsExist(RequestFile, FILE_COMMON))
    {
        Print("Screenshot request detected!");
        ProcessScreenshotRequest();
    }
}

//+------------------------------------------------------------------+
//| Process screenshot request - Capture all timeframes               |
//+------------------------------------------------------------------+
void ProcessScreenshotRequest()
{
    // リクエストファイルを読み込み
    int handle = FileOpen(RequestFile, FILE_READ|FILE_TXT|FILE_COMMON);
    if(handle == INVALID_HANDLE)
    {
        Print("Failed to open request file");
        return;
    }

    string content = FileReadString(handle);
    FileClose(handle);

    Print("Request content: ", content);

    // 銘柄名を取得
    string symbol = Symbol();
    int capturedCount = 0;
    int totalTimeframes = ArraySize(TIMEFRAMES_TO_CAPTURE);

    Print("Starting multi-timeframe capture for ", symbol, " (", totalTimeframes, " timeframes)");

    // 各時間足のスクリーンショットを取得
    for(int i = 0; i < totalTimeframes; i++)
    {
        ENUM_TIMEFRAMES tf = TIMEFRAMES_TO_CAPTURE[i];
        string tfName = TIMEFRAME_NAMES_TO_CAPTURE[i];

        // 時間足チャートを開く（既存なら既存のIDを返す）
        long chartId = ChartOpen(symbol, tf);
        if(chartId <= 0)
        {
            Print("Failed to open chart for ", symbol, " ", tfName, " Error: ", GetLastError());
            continue;
        }

        Print("Chart opened: ", symbol, " ", tfName, " ChartID: ", chartId);

        // ソースチャートから水平線をコピー
        int linesCopied = CopyHorizontalLinesToChart(sourceChartId, chartId);
        if(linesCopied > 0)
        {
            Print("Copied ", linesCopied, " horizontal lines to chart ", tfName);
        }

        // チャートの読み込み待機
        Sleep(ChartLoadWait);
        ChartRedraw(chartId);

        // スクリーンショット取得
        // ChartScreenShotはMQL5/Filesに保存される（Common/Filesへのコピーは不要）
        // Pythonはterminal_pathを使ってMQL5/Filesから直接読み込む
        string localFilename = OutputPrefix + symbol + "_" + tfName + ".png";
        if(ChartScreenShot(chartId, localFilename, ImageWidth, ImageHeight, ALIGN_RIGHT))
        {
            Print("Screenshot saved: ", localFilename);
            capturedCount++;
        }
        else
        {
            Print("Screenshot failed: ", localFilename, " Error: ", GetLastError());
        }
    }

    // 完了通知ファイルを作成（成功した場合のみ）
    // ※ count=0 の場合は完了ファイルを作成しない（EA版に任せる）
    if(capturedCount > 0)
    {
        WriteCompletionFileMulti(symbol, capturedCount);
    }
    else
    {
        Print("No screenshots captured - skipping completion file (use ChartExporterEA instead)");
    }

    // リクエストファイルを削除しない（EA版が処理できるように残す）
    // ※ インジケータ版はChartOpen()が使えないため、常に失敗する
    // if(!FileDelete(RequestFile, FILE_COMMON))
    // {
    //     Print("Warning: Could not delete request file");
    // }

    Print("Multi-timeframe screenshot completed: ", capturedCount, "/", totalTimeframes, " captured");
}

//+------------------------------------------------------------------+
//| Get timeframe name string                                         |
//+------------------------------------------------------------------+
string GetTimeframeName(ENUM_TIMEFRAMES tf)
{
    switch(tf)
    {
        case PERIOD_M1:  return "M1";
        case PERIOD_M5:  return "M5";
        case PERIOD_M15: return "M15";
        case PERIOD_M30: return "M30";
        case PERIOD_H1:  return "H1";
        case PERIOD_H4:  return "H4";
        case PERIOD_D1:  return "D1";
        case PERIOD_W1:  return "W1";
        case PERIOD_MN1: return "MN1";
        default:         return "UNKNOWN";
    }
}

//+------------------------------------------------------------------+
//| Write completion notification file (single timeframe - legacy)    |
//+------------------------------------------------------------------+
void WriteCompletionFile(string symbol, string timeframe)
{
    string completionFile = "screenshot_complete.txt";
    int handle = FileOpen(completionFile, FILE_WRITE|FILE_TXT|FILE_COMMON);
    if(handle != INVALID_HANDLE)
    {
        string content = "{\n";
        content += "  \"symbol\": \"" + symbol + "\",\n";
        content += "  \"timeframe\": \"" + timeframe + "\",\n";
        content += "  \"timestamp\": \"" + TimeToString(TimeCurrent(), TIME_DATE|TIME_MINUTES|TIME_SECONDS) + "\",\n";
        content += "  \"file\": \"" + OutputPrefix + symbol + "_" + timeframe + ".png\"\n";
        content += "}\n";

        FileWriteString(handle, content);
        FileClose(handle);
        Print("Completion file written: ", completionFile);
    }
}

//+------------------------------------------------------------------+
//| Write completion notification file (multi-timeframe)              |
//+------------------------------------------------------------------+
void WriteCompletionFileMulti(string symbol, int count)
{
    string completionFile = "screenshot_complete.txt";
    int handle = FileOpen(completionFile, FILE_WRITE|FILE_TXT|FILE_COMMON);
    if(handle != INVALID_HANDLE)
    {
        // ターミナルのデータフォルダパスを取得してPythonに伝える
        string terminalPath = TerminalInfoString(TERMINAL_DATA_PATH);

        string content = "{\n";
        content += "  \"symbol\": \"" + symbol + "\",\n";
        content += "  \"count\": " + IntegerToString(count) + ",\n";
        content += "  \"timeframes\": [\"D1\", \"H4\", \"M15\", \"M5\", \"M1\"],\n";
        content += "  \"timestamp\": \"" + TimeToString(TimeCurrent(), TIME_DATE|TIME_MINUTES|TIME_SECONDS) + "\",\n";
        content += "  \"prefix\": \"" + OutputPrefix + symbol + "_\",\n";
        content += "  \"terminal_path\": \"" + terminalPath + "\"\n";
        content += "}\n";

        FileWriteString(handle, content);
        FileClose(handle);
        Print("Completion file written: ", completionFile, " (", count, " timeframes)");
        Print("Terminal path: ", terminalPath);
    }
}

//+------------------------------------------------------------------+
//| Copy horizontal lines from ALL open charts to target chart        |
//+------------------------------------------------------------------+
int CopyHorizontalLinesToChart(long srcChartId, long dstChartId)
{
    int copied = 0;
    string currentSymbol = Symbol();

    // すべての開いているチャートをスキャン
    long chartId = ChartFirst();
    while(chartId >= 0)
    {
        // 同じ銘柄のチャートから水平線をコピー
        string chartSymbol = ChartSymbol(chartId);
        if(chartSymbol == currentSymbol)
        {
            int totalObjects = ObjectsTotal(chartId, 0, OBJ_HLINE);

            for(int i = 0; i < totalObjects; i++)
            {
                string objName = ObjectName(chartId, i, 0, OBJ_HLINE);
                if(objName == "") continue;

                // ターゲットチャートに既に同じ価格のラインがあればスキップ
                double price = ObjectGetDouble(chartId, objName, OBJPROP_PRICE);

                // ユニークな名前を作成（元チャートIDを含む）
                string newName = objName;
                if(chartId != dstChartId)
                {
                    newName = objName + "_" + IntegerToString(chartId);
                }

                // ターゲットチャートに同名のオブジェクトが既に存在する場合は削除
                if(ObjectFind(dstChartId, newName) >= 0)
                {
                    ObjectDelete(dstChartId, newName);
                }

                // 元の水平線のプロパティを取得
                color lineColor = (color)ObjectGetInteger(chartId, objName, OBJPROP_COLOR);
                int lineWidth = (int)ObjectGetInteger(chartId, objName, OBJPROP_WIDTH);
                ENUM_LINE_STYLE lineStyle = (ENUM_LINE_STYLE)ObjectGetInteger(chartId, objName, OBJPROP_STYLE);
                string lineText = ObjectGetString(chartId, objName, OBJPROP_TEXT);

                // ターゲットチャートに水平線を作成
                if(ObjectCreate(dstChartId, newName, OBJ_HLINE, 0, 0, price))
                {
                    ObjectSetInteger(dstChartId, newName, OBJPROP_COLOR, lineColor);
                    ObjectSetInteger(dstChartId, newName, OBJPROP_WIDTH, lineWidth);
                    ObjectSetInteger(dstChartId, newName, OBJPROP_STYLE, lineStyle);
                    ObjectSetString(dstChartId, newName, OBJPROP_TEXT, lineText);
                    ObjectSetInteger(dstChartId, newName, OBJPROP_BACK, false);
                    copied++;
                }
            }
        }

        chartId = ChartNext(chartId);
    }

    return copied;
}
//+------------------------------------------------------------------+
