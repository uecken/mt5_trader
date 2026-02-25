//+------------------------------------------------------------------+
//|                                            ChartExporterEA.mq5   |
//|                       チャートスクリーンショット自動エクスポート    |
//|       Pythonからのリクエストを検知してChartScreenShot()を実行     |
//|       全時間足(D1, H4, M15, M5, M1)を自動キャプチャ               |
//|       ※ ChartOpen()はEAでのみ使用可能なためEAとして実装          |
//+------------------------------------------------------------------+
#property copyright "MT5 Trader System"
#property version   "3.00"
#property strict

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

//--- Charts opened by this EA (to close them later if needed)
long openedChartIds[];

//+------------------------------------------------------------------+
//| Expert initialization function                                     |
//+------------------------------------------------------------------+
int OnInit()
{
    EventSetTimer(CheckInterval);
    Print("ChartExporterEA initialized. Waiting for requests...");
    Print("Request file: ", RequestFile);
    Print("This EA can open new charts (unlike indicators)");
    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                   |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    EventKillTimer();

    // Close any charts we opened
    for(int i = 0; i < ArraySize(openedChartIds); i++)
    {
        if(openedChartIds[i] > 0)
        {
            ChartClose(openedChartIds[i]);
        }
    }
    ArrayResize(openedChartIds, 0);

    Print("ChartExporterEA stopped");
}

//+------------------------------------------------------------------+
//| Expert tick function (required but not used)                       |
//+------------------------------------------------------------------+
void OnTick()
{
    // Not used - we rely on timer events
}

//+------------------------------------------------------------------+
//| Timer event handler - check for screenshot requests                |
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
//| Find existing chart with specific symbol and timeframe             |
//+------------------------------------------------------------------+
long FindExistingChart(string symbol, ENUM_TIMEFRAMES timeframe)
{
    long chartId = ChartFirst();
    while(chartId >= 0)
    {
        if(ChartSymbol(chartId) == symbol && ChartPeriod(chartId) == timeframe)
        {
            return chartId;
        }
        chartId = ChartNext(chartId);
    }
    return -1;  // Not found
}

//+------------------------------------------------------------------+
//| Process screenshot request - Capture all timeframes                |
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

    // 銘柄名を取得（このEAがアタッチされているチャートの銘柄）
    string symbol = Symbol();
    int capturedCount = 0;
    int totalTimeframes = ArraySize(TIMEFRAMES_TO_CAPTURE);

    // 開いたチャートIDを追跡
    ArrayResize(openedChartIds, 0);

    // デバッグ: このEAがアタッチされているチャートの情報
    long myChartId = ChartID();
    int myHLines = ObjectsTotal(myChartId, 0, OBJ_HLINE);
    int myAllObjects = ObjectsTotal(myChartId, -1, -1);
    Print("EA attached to chart ", myChartId, " (", EnumToString(Period()), ")");
    Print("  This chart has ", myHLines, " horizontal lines, ", myAllObjects, " total objects");

    // すべてのチャートの水平線を事前にスキャン
    Print("=== Scanning all charts for horizontal lines ===");
    long scanId = ChartFirst();
    while(scanId >= 0)
    {
        string scanSymbol = ChartSymbol(scanId);
        if(scanSymbol == symbol)
        {
            int hlines = ObjectsTotal(scanId, 0, OBJ_HLINE);
            int allObj = ObjectsTotal(scanId, -1, -1);
            ENUM_TIMEFRAMES scanTf = ChartPeriod(scanId);
            Print("  Chart ", scanId, " (", EnumToString(scanTf), "): ", hlines, " HLines, ", allObj, " total objects");

            // 最初の水平線の名前と価格を出力
            if(hlines > 0)
            {
                string firstName = ObjectName(scanId, 0, 0, OBJ_HLINE);
                double firstPrice = ObjectGetDouble(scanId, firstName, OBJPROP_PRICE);
                Print("    First HLine: ", firstName, " at ", DoubleToString(firstPrice, 2));
            }
        }
        scanId = ChartNext(scanId);
    }
    Print("=== End scan ===");

    Print("Starting multi-timeframe capture for ", symbol, " (", totalTimeframes, " timeframes)");

    // 各時間足のスクリーンショットを取得
    for(int i = 0; i < totalTimeframes; i++)
    {
        ENUM_TIMEFRAMES tf = TIMEFRAMES_TO_CAPTURE[i];
        string tfName = TIMEFRAME_NAMES_TO_CAPTURE[i];

        // まず既存のチャートを探す
        long chartId = FindExistingChart(symbol, tf);
        bool newlyOpened = false;

        if(chartId < 0)
        {
            // 既存のチャートがない場合、新しく開く
            chartId = ChartOpen(symbol, tf);
            if(chartId <= 0)
            {
                Print("Failed to open chart for ", symbol, " ", tfName, " Error: ", GetLastError());
                continue;
            }
            newlyOpened = true;

            // 開いたチャートを追跡
            int size = ArraySize(openedChartIds);
            ArrayResize(openedChartIds, size + 1);
            openedChartIds[size] = chartId;

            Print("New chart opened: ", symbol, " ", tfName, " ChartID: ", chartId);
        }
        else
        {
            Print("Using existing chart: ", symbol, " ", tfName, " ChartID: ", chartId);
        }

        // まずチャートを再描画して現在の状態を確定
        ChartRedraw(chartId);
        Sleep(200);

        // すべての開いているチャートから水平線をコピー
        int linesCopied = CopyHorizontalLinesFromAllCharts(chartId);
        if(linesCopied > 0)
        {
            Print("Copied ", linesCopied, " horizontal lines to chart ", tfName);
        }

        // 水平線コピー後にチャートを再描画
        ChartRedraw(chartId);

        // 十分な待機時間（水平線が確実に描画されるように）
        Sleep(ChartLoadWait + 500);

        // 再度描画を強制
        ChartRedraw(chartId);
        Sleep(200);

        // スクリーンショット取得
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

        // 新しく開いたチャートは後でクリーンアップ用に保持
        // （即座に閉じるとスクリーンショットが不完全になる可能性があるため）
    }

    // 完了通知ファイルを作成
    WriteCompletionFileMulti(symbol, capturedCount);

    // リクエストファイルを削除
    if(!FileDelete(RequestFile, FILE_COMMON))
    {
        Print("Warning: Could not delete request file");
    }

    Print("Multi-timeframe screenshot completed: ", capturedCount, "/", totalTimeframes, " captured");

    // 少し待ってから開いたチャートを閉じる
    Sleep(1000);
    for(int i = 0; i < ArraySize(openedChartIds); i++)
    {
        if(openedChartIds[i] > 0)
        {
            ChartClose(openedChartIds[i]);
            Print("Closed temporary chart: ", openedChartIds[i]);
        }
    }
    ArrayResize(openedChartIds, 0);
}

//+------------------------------------------------------------------+
//| Copy horizontal lines from ALL open charts to target chart         |
//+------------------------------------------------------------------+
int CopyHorizontalLinesFromAllCharts(long dstChartId)
{
    int copied = 0;
    string currentSymbol = Symbol();

    // デバッグ: ターゲットチャートの既存の水平線をログ出力
    int existingLines = ObjectsTotal(dstChartId, 0, OBJ_HLINE);
    Print("Target chart ", dstChartId, " has ", existingLines, " existing horizontal lines");

    // ターゲットチャートの既存の水平線を削除（コピーされた線のみ）
    for(int i = existingLines - 1; i >= 0; i--)
    {
        string objName = ObjectName(dstChartId, i, 0, OBJ_HLINE);
        // コピーされた水平線（名前に_copied_が含まれる）のみ削除
        if(StringFind(objName, "_copied_") >= 0)
        {
            ObjectDelete(dstChartId, objName);
        }
        else
        {
            // ユーザーの水平線はログに出力（最初の5本のみ）
            if(i < 5)
            {
                double price = ObjectGetDouble(dstChartId, objName, OBJPROP_PRICE);
                Print("  Existing line: ", objName, " at price ", DoubleToString(price, 2));
            }
        }
    }

    // すべての開いているチャートをスキャン
    long chartId = ChartFirst();
    int chartCount = 0;
    while(chartId >= 0)
    {
        // 同じ銘柄のチャートから水平線をコピー（ターゲット自身は除く）
        string chartSymbol = ChartSymbol(chartId);
        if(chartSymbol == currentSymbol && chartId != dstChartId)
        {
            int totalObjects = ObjectsTotal(chartId, 0, OBJ_HLINE);
            ENUM_TIMEFRAMES chartTf = ChartPeriod(chartId);
            Print("Source chart ", chartId, " (", EnumToString(chartTf), ") has ", totalObjects, " horizontal lines");
            chartCount++;

            for(int i = 0; i < totalObjects; i++)
            {
                string objName = ObjectName(chartId, i, 0, OBJ_HLINE);
                if(objName == "") continue;

                // 元の水平線のプロパティを取得
                double price = ObjectGetDouble(chartId, objName, OBJPROP_PRICE);
                color lineColor = (color)ObjectGetInteger(chartId, objName, OBJPROP_COLOR);
                int lineWidth = (int)ObjectGetInteger(chartId, objName, OBJPROP_WIDTH);
                ENUM_LINE_STYLE lineStyle = (ENUM_LINE_STYLE)ObjectGetInteger(chartId, objName, OBJPROP_STYLE);
                string lineText = ObjectGetString(chartId, objName, OBJPROP_TEXT);

                // ユニークな名前を作成
                string newName = objName + "_copied_" + IntegerToString(chartId);

                // ターゲットチャートに同名のオブジェクトが既に存在する場合は削除
                if(ObjectFind(dstChartId, newName) >= 0)
                {
                    ObjectDelete(dstChartId, newName);
                }

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
//| Write completion notification file (multi-timeframe)               |
//+------------------------------------------------------------------+
void WriteCompletionFileMulti(string symbol, int count)
{
    // EA版は別の完了ファイル名を使用（インジケータ版との競合を避けるため）
    // FILE_ANSI を使用してPythonが読めるエンコーディングで書き込む
    string completionFile = "screenshot_complete_ea.txt";
    int handle = FileOpen(completionFile, FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
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
