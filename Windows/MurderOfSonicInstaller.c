#define WIN32_LEAN_AND_MEAN

#include <windows.h>
#include <commctrl.h>
#include <wchar.h>

#define APP_TITLE L"VN Revival Languages for The Murder of Sonic the Hedgehog"
#define IDI_APP 101
#define ID_LANGUAGE 1001
#define ID_INSTALL 1002

static const COLORREF COLOR_SIDEBAR = RGB(48, 34, 27);
static const COLORREF COLOR_GOLD = RGB(218, 178, 77);
static const COLORREF COLOR_GOLD_DARK = RGB(173, 132, 42);
static const COLORREF COLOR_CREAM = RGB(249, 244, 229);
static const COLORREF COLOR_CARD = RGB(255, 252, 243);
static const COLORREF COLOR_TEXT = RGB(49, 42, 36);
static const COLORREF COLOR_MUTED = RGB(116, 105, 94);

static HFONT headingFont;
static HFONT bodyFont;
static HFONT smallFont;
static HFONT brandFont;
static HICON appIcon;
static BOOL ownsAppIcon;
static HWND languageCombo;
static HWND installButton;
static HWINSTA interactiveWindowStation;
static HDESK interactiveDesktop;

static const wchar_t *languages[] = {
    L"中文（简体）", L"русский", L"español", L"español (Latinoamérica)",
    L"português (Brasil)", L"日本語", L"Deutsch", L"한국어", L"français", L"Türkçe",
    L"polski", L"中文（繁體）", L"italiano", L"ไทย", L"Tiếng Việt", L"Bahasa Indonesia",
    L"українська", L"العربية", L"čeština", L"magyar", L"Nederlands", L"فارسی",
    L"română", L"हिन्दी", L"Filipino", L"Ελληνικά", L"български", L"српски",
    L"Kiswahili", L"עברית"
};

static void setFont(HWND control, HFONT font) {
    SendMessageW(control, WM_SETFONT, (WPARAM)font, TRUE);
}

static void drawTextLine(HDC dc, HFONT font, COLORREF color, const wchar_t *text, RECT bounds, UINT format) {
    HFONT previous = (HFONT)SelectObject(dc, font);
    SetTextColor(dc, color);
    SetBkMode(dc, TRANSPARENT);
    DrawTextW(dc, text, -1, &bounds, format);
    SelectObject(dc, previous);
}

static void paintInterface(HWND window) {
    PAINTSTRUCT paint;
    HDC dc = BeginPaint(window, &paint);
    RECT client;
    GetClientRect(window, &client);

    HBRUSH cream = CreateSolidBrush(COLOR_CREAM);
    FillRect(dc, &client, cream);
    DeleteObject(cream);

    RECT sidebar = {0, 0, 244, client.bottom};
    HBRUSH sidebarBrush = CreateSolidBrush(COLOR_SIDEBAR);
    FillRect(dc, &sidebar, sidebarBrush);
    DeleteObject(sidebarBrush);

    RECT goldRule = {244, 0, 250, client.bottom};
    HBRUSH goldBrush = CreateSolidBrush(COLOR_GOLD);
    FillRect(dc, &goldRule, goldBrush);
    DeleteObject(goldBrush);

    RECT iconCard = {42, 42, 202, 202};
    HBRUSH iconBrush = CreateSolidBrush(RGB(255, 248, 224));
    HPEN iconPen = CreatePen(PS_SOLID, 2, COLOR_GOLD);
    HGDIOBJ oldBrush = SelectObject(dc, iconBrush);
    HGDIOBJ oldPen = SelectObject(dc, iconPen);
    RoundRect(dc, iconCard.left, iconCard.top, iconCard.right, iconCard.bottom, 26, 26);
    SelectObject(dc, oldBrush);
    SelectObject(dc, oldPen);
    DeleteObject(iconBrush);
    DeleteObject(iconPen);
    if (appIcon) DrawIconEx(dc, 56, 56, appIcon, 132, 132, 0, NULL, DI_NORMAL);

    RECT brand = {38, 224, 210, 256};
    drawTextLine(dc, brandFont, COLOR_GOLD, L"VN REVIVAL", brand, DT_CENTER | DT_SINGLELINE | DT_VCENTER);
    RECT gameTitle = {34, 267, 214, 352};
    drawTextLine(dc, bodyFont, RGB(255, 249, 230),
        L"THE MURDER OF SONIC\nTHE HEDGEHOG", gameTitle,
        DT_CENTER | DT_WORDBREAK | DT_NOPREFIX);
    RECT sideNote = {40, 400, 208, 446};
    drawTextLine(dc, smallFont, RGB(199, 185, 166),
        L"30 community localizations", sideNote,
        DT_CENTER | DT_WORDBREAK | DT_NOPREFIX);

    RECT heading = {292, 50, 700, 90};
    drawTextLine(dc, headingFont, COLOR_TEXT, L"Choose a language", heading,
        DT_LEFT | DT_SINGLELINE | DT_VCENTER);
    RECT intro = {294, 94, 700, 134};
    drawTextLine(dc, bodyFont, COLOR_MUTED,
        L"Select the language you want to use in the game.", intro,
        DT_LEFT | DT_WORDBREAK | DT_NOPREFIX);

    RECT shadow = {291, 154, 707, 352};
    HBRUSH shadowBrush = CreateSolidBrush(RGB(224, 216, 198));
    oldBrush = SelectObject(dc, shadowBrush);
    oldPen = SelectObject(dc, GetStockObject(NULL_PEN));
    RoundRect(dc, shadow.left, shadow.top, shadow.right, shadow.bottom, 20, 20);
    SelectObject(dc, oldBrush);
    SelectObject(dc, oldPen);
    DeleteObject(shadowBrush);

    RECT card = {286, 148, 702, 346};
    HBRUSH cardBrush = CreateSolidBrush(COLOR_CARD);
    HPEN cardPen = CreatePen(PS_SOLID, 1, RGB(229, 218, 195));
    oldBrush = SelectObject(dc, cardBrush);
    oldPen = SelectObject(dc, cardPen);
    RoundRect(dc, card.left, card.top, card.right, card.bottom, 20, 20);
    SelectObject(dc, oldBrush);
    SelectObject(dc, oldPen);
    DeleteObject(cardBrush);
    DeleteObject(cardPen);

    RECT label = {320, 176, 660, 204};
    drawTextLine(dc, smallFont, COLOR_MUTED, L"GAME LANGUAGE", label,
        DT_LEFT | DT_SINGLELINE | DT_VCENTER);
    RECT helper = {320, 254, 684, 280};
    drawTextLine(dc, smallFont, COLOR_MUTED,
        L"You can change it later by running the installer again.", helper,
        DT_LEFT | DT_SINGLELINE | DT_VCENTER);

    RECT footer = {292, 405, 700, 436};
    drawTextLine(dc, smallFont, COLOR_MUTED,
        L"Steam • Game version 1.01 • Installer interface: English", footer,
        DT_LEFT | DT_SINGLELINE | DT_VCENTER);

    EndPaint(window, &paint);
}

static void drawInstallButton(const DRAWITEMSTRUCT *item) {
    COLORREF background = (item->itemState & ODS_SELECTED) ? COLOR_GOLD_DARK : COLOR_GOLD;
    HBRUSH brush = CreateSolidBrush(background);
    HPEN pen = CreatePen(PS_SOLID, 1, COLOR_GOLD_DARK);
    HGDIOBJ oldBrush = SelectObject(item->hDC, brush);
    HGDIOBJ oldPen = SelectObject(item->hDC, pen);
    RoundRect(item->hDC, item->rcItem.left, item->rcItem.top,
        item->rcItem.right, item->rcItem.bottom, 12, 12);
    SelectObject(item->hDC, oldBrush);
    SelectObject(item->hDC, oldPen);
    DeleteObject(brush);
    DeleteObject(pen);

    RECT textBounds = item->rcItem;
    if (item->itemState & ODS_SELECTED) OffsetRect(&textBounds, 0, 1);
    drawTextLine(item->hDC, bodyFont, RGB(39, 29, 20), L"Install localization",
        textBounds, DT_CENTER | DT_SINGLELINE | DT_VCENTER);

    if (item->itemState & ODS_FOCUS) {
        RECT focus = item->rcItem;
        InflateRect(&focus, -4, -4);
        DrawFocusRect(item->hDC, &focus);
    }
}

static LRESULT CALLBACK windowProcedure(HWND window, UINT message, WPARAM wParam, LPARAM lParam) {
    switch (message) {
        case WM_CREATE: {
            headingFont = CreateFontW(-32, 0, 0, 0, FW_SEMIBOLD, FALSE, FALSE, FALSE,
                DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
            bodyFont = CreateFontW(-20, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
            smallFont = CreateFontW(-15, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
            brandFont = CreateFontW(-23, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE,
                DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");

            languageCombo = CreateWindowW(WC_COMBOBOXW, NULL,
                WS_CHILD | WS_VISIBLE | WS_TABSTOP | CBS_DROPDOWNLIST | WS_VSCROLL,
                320, 210, 348, 420, window, (HMENU)ID_LANGUAGE, NULL, NULL);
            setFont(languageCombo, bodyFont);
            for (size_t i = 0; i < sizeof(languages) / sizeof(languages[0]); ++i) {
                SendMessageW(languageCombo, CB_ADDSTRING, 0, (LPARAM)languages[i]);
            }
            SendMessageW(languageCombo, CB_SETCURSEL, 1, 0);

            installButton = CreateWindowW(L"BUTTON", L"Install localization",
                WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_OWNERDRAW,
                450, 289, 218, 44, window, (HMENU)ID_INSTALL, NULL, NULL);
            setFont(installButton, bodyFont);
            return 0;
        }
        case WM_PAINT:
            paintInterface(window);
            return 0;
        case WM_ERASEBKGND:
            return 1;
        case WM_DRAWITEM:
            if ((UINT)wParam == ID_INSTALL) {
                drawInstallButton((const DRAWITEMSTRUCT *)lParam);
                return TRUE;
            }
            break;
        case WM_COMMAND:
            if (LOWORD(wParam) == ID_INSTALL) {
                MessageBoxW(window,
                    L"This development preview does not reinstall the game.\r\nThe verified Windows test payload is already installed.",
                    APP_TITLE, MB_OK | MB_ICONINFORMATION);
                return 0;
            }
            break;
        case WM_DESTROY:
            DeleteObject(headingFont);
            DeleteObject(bodyFont);
            DeleteObject(smallFont);
            DeleteObject(brandFont);
            if (appIcon && ownsAppIcon) DestroyIcon(appIcon);
            PostQuitMessage(0);
            return 0;
    }
    return DefWindowProcW(window, message, wParam, lParam);
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR commandLine, int showCommand) {
    (void)previous;
    (void)commandLine;
    (void)showCommand;
    INITCOMMONCONTROLSEX controls = { sizeof(controls), ICC_STANDARD_CLASSES };
    InitCommonControlsEx(&controls);

    interactiveWindowStation = OpenWindowStationW(L"WinSta0", FALSE, WINSTA_ALL_ACCESS);
    if (interactiveWindowStation) {
        SetProcessWindowStation(interactiveWindowStation);
        interactiveDesktop = OpenDesktopW(L"Default", 0, FALSE, MAXIMUM_ALLOWED);
        if (interactiveDesktop) SetThreadDesktop(interactiveDesktop);
    }

    appIcon = (HICON)LoadImageW(instance, MAKEINTRESOURCEW(IDI_APP), IMAGE_ICON,
        256, 256, LR_DEFAULTCOLOR);
    ownsAppIcon = appIcon != NULL;
    if (!appIcon) appIcon = LoadIconW(NULL, IDI_APPLICATION);

    WNDCLASSEXW windowClass = {0};
    windowClass.cbSize = sizeof(windowClass);
    windowClass.lpfnWndProc = windowProcedure;
    windowClass.hInstance = instance;
    windowClass.hCursor = LoadCursorW(NULL, IDC_ARROW);
    windowClass.hIcon = appIcon;
    windowClass.hIconSm = appIcon;
    windowClass.hbrBackground = NULL;
    windowClass.lpszClassName = L"VNRevivalMurderOfSonicInstaller";
    if (!RegisterClassExW(&windowClass)) return 1;

    HWND window = CreateWindowExW(0, windowClass.lpszClassName, APP_TITLE,
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
        CW_USEDEFAULT, CW_USEDEFAULT, 760, 500,
        NULL, NULL, instance, NULL);
    if (!window) return 2;

    ShowWindow(window, SW_SHOWNORMAL);
    UpdateWindow(window);
    SetWindowPos(window, HWND_TOPMOST, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW);
    SetForegroundWindow(window);
    SetWindowPos(window, HWND_NOTOPMOST, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW);

    MSG message;
    while (GetMessageW(&message, NULL, 0, 0) > 0) {
        TranslateMessage(&message);
        DispatchMessageW(&message);
    }
    if (interactiveDesktop) CloseDesktop(interactiveDesktop);
    if (interactiveWindowStation) CloseWindowStation(interactiveWindowStation);
    return (int)message.wParam;
}
