#define WIN32_LEAN_AND_MEAN

#include <windows.h>
#include <commctrl.h>
#include <shellapi.h>
#include <shlobj.h>
#include <wchar.h>

#define APP_TITLE L"VN Revival Languages for The Murder of Sonic the Hedgehog"
#define IDI_APP 101
#define ID_LANGUAGE 1001
#define ID_INSTALL 1002
#define ID_PROGRESS 1003
#define ID_CHOOSE_GAME 1004
#define WM_INSTALL_COMPLETE (WM_APP + 1)

enum InstallState { STATE_READY, STATE_WORKING, STATE_SUCCESS, STATE_ERROR };

typedef struct {
    HWND window;
    wchar_t runtimeCode[16];
    wchar_t gamePath[MAX_PATH];
} InstallRequest;

typedef struct {
    BOOL success;
    wchar_t message[1024];
} InstallResult;

static const COLORREF COLOR_SIDEBAR = RGB(48, 34, 27);
static const COLORREF COLOR_GOLD = RGB(218, 178, 77);
static const COLORREF COLOR_GOLD_DARK = RGB(173, 132, 42);
static const COLORREF COLOR_CREAM = RGB(249, 244, 229);
static const COLORREF COLOR_CARD = RGB(255, 252, 243);
static const COLORREF COLOR_TEXT = RGB(49, 42, 36);
static const COLORREF COLOR_MUTED = RGB(116, 105, 94);
static const COLORREF COLOR_SUCCESS = RGB(57, 120, 72);
static const COLORREF COLOR_ERROR = RGB(166, 54, 48);

static HFONT headingFont;
static HFONT bodyFont;
static HFONT smallFont;
static HFONT brandFont;
static HICON appIcon;
static BOOL ownsAppIcon;
static HWND languageCombo;
static HWND installButton;
static HWND chooseGameButton;
static HWND progressBar;
static HWINSTA interactiveWindowStation;
static HDESK interactiveDesktop;
static enum InstallState installState = STATE_READY;
static wchar_t statusMessage[1024] = L"Ready to install.";
static wchar_t selectedGamePath[MAX_PATH] = L"";

static const wchar_t *languages[] = {
    L"中文（简体）", L"русский", L"español", L"español latinoamericano",
    L"português (Brasil)", L"日本語", L"Deutsch", L"한국어", L"français", L"Türkçe",
    L"polski", L"中文（繁體）", L"italiano", L"ไทย", L"Tiếng Việt", L"Bahasa Indonesia",
    L"українська", L"العربية", L"čeština", L"magyar", L"Nederlands", L"فارسی",
    L"română", L"हिन्दी", L"Filipino", L"Ελληνικά", L"български", L"српски",
    L"Kiswahili", L"עברית"
};

static const wchar_t *runtimeCodes[] = {
    L"zh", L"ru", L"es", L"es-419", L"pt-BR", L"ja", L"de", L"ko", L"fr", L"tr",
    L"pl", L"zh-TW", L"it", L"th", L"vi", L"id", L"uk", L"ar", L"cs", L"hu",
    L"nl", L"fa", L"ro", L"hi", L"fil", L"el", L"bg", L"sr", L"sw", L"he"
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

static const wchar_t *buttonLabel(void) {
    if (installState == STATE_WORKING) return L"Installing…";
    if (installState == STATE_SUCCESS) return L"Launch game";
    if (installState == STATE_ERROR) return L"Retry";
    return L"Install localization";
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
    drawTextLine(dc, bodyFont, RGB(255, 249, 230), L"THE MURDER OF SONIC\nTHE HEDGEHOG",
        gameTitle, DT_CENTER | DT_WORDBREAK | DT_NOPREFIX);
    RECT sideNote = {40, 414, 208, 460};
    drawTextLine(dc, smallFont, RGB(199, 185, 166), L"30 community localizations",
        sideNote, DT_CENTER | DT_WORDBREAK | DT_NOPREFIX);

    RECT heading = {292, 42, 700, 84};
    drawTextLine(dc, headingFont, COLOR_TEXT, L"Choose a language", heading,
        DT_LEFT | DT_SINGLELINE | DT_VCENTER);
    RECT intro = {294, 86, 700, 140};
    drawTextLine(dc, bodyFont, COLOR_MUTED, L"Select the language you want to use in the game.",
        intro, DT_LEFT | DT_WORDBREAK | DT_NOPREFIX);

    RECT shadow = {291, 158, 707, 431};
    HBRUSH shadowBrush = CreateSolidBrush(RGB(224, 216, 198));
    oldBrush = SelectObject(dc, shadowBrush);
    oldPen = SelectObject(dc, GetStockObject(NULL_PEN));
    RoundRect(dc, shadow.left, shadow.top, shadow.right, shadow.bottom, 20, 20);
    SelectObject(dc, oldBrush);
    SelectObject(dc, oldPen);
    DeleteObject(shadowBrush);
    RECT card = {286, 152, 702, 425};
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
    RECT helper = {320, 254, 674, 298};
    drawTextLine(dc, smallFont, COLOR_MUTED,
        L"Run this installer again whenever you want to switch language.", helper,
        DT_LEFT | DT_WORDBREAK | DT_NOPREFIX);

    COLORREF statusColor = COLOR_MUTED;
    if (installState == STATE_SUCCESS) statusColor = COLOR_SUCCESS;
    if (installState == STATE_ERROR) statusColor = COLOR_ERROR;
    RECT status = {320, 370, 672, 414};
    drawTextLine(dc, smallFont, statusColor, statusMessage, status,
        DT_LEFT | DT_WORDBREAK | DT_NOPREFIX | DT_END_ELLIPSIS);
    RECT footer = {292, 460, 700, 490};
    drawTextLine(dc, smallFont, COLOR_MUTED,
        L"Steam • Game version 1.01 • Installer interface: English", footer,
        DT_LEFT | DT_SINGLELINE | DT_VCENTER);
    EndPaint(window, &paint);
}

static void drawInstallButton(const DRAWITEMSTRUCT *item) {
    COLORREF background = (item->itemState & ODS_SELECTED) ? COLOR_GOLD_DARK : COLOR_GOLD;
    if (installState == STATE_WORKING) background = RGB(212, 204, 183);
    HBRUSH brush = CreateSolidBrush(background);
    HPEN pen = CreatePen(PS_SOLID, 1,
        installState == STATE_WORKING ? RGB(183, 174, 153) : COLOR_GOLD_DARK);
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
    drawTextLine(item->hDC, bodyFont, RGB(39, 29, 20), buttonLabel(),
        textBounds, DT_CENTER | DT_SINGLELINE | DT_VCENTER);
    if (item->itemState & ODS_FOCUS) {
        RECT focus = item->rcItem;
        InflateRect(&focus, -4, -4);
        DrawFocusRect(item->hDC, &focus);
    }
}

static void drawSecondaryButton(const DRAWITEMSTRUCT *item) {
    COLORREF background = (item->itemState & ODS_SELECTED)
        ? RGB(237, 228, 207) : COLOR_CARD;
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
    drawTextLine(item->hDC, smallFont, COLOR_TEXT, L"Game folder…",
        textBounds, DT_CENTER | DT_SINGLELINE | DT_VCENTER);
    if (item->itemState & ODS_FOCUS) {
        RECT focus = item->rcItem;
        InflateRect(&focus, -4, -4);
        DrawFocusRect(item->hDC, &focus);
    }
}

static void chooseGameFolder(HWND window) {
    BROWSEINFOW browse = {0};
    browse.hwndOwner = window;
    browse.lpszTitle = L"Choose the Steam folder for The Murder of Sonic the Hedgehog";
    browse.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE;
    LPITEMIDLIST item = SHBrowseForFolderW(&browse);
    if (!item) return;
    wchar_t path[MAX_PATH];
    BOOL resolved = SHGetPathFromIDListW(item, path);
    CoTaskMemFree(item);
    if (!resolved) {
        installState = STATE_ERROR;
        wcscpy_s(statusMessage, 1024, L"The selected folder could not be read.");
        InvalidateRect(window, NULL, FALSE);
        return;
    }
    wcsncpy_s(selectedGamePath, MAX_PATH, path, _TRUNCATE);
    installState = STATE_READY;
    wcscpy_s(statusMessage, 1024, L"Game folder selected. Ready to install.");
    InvalidateRect(window, NULL, FALSE);
}

static BOOL getModuleDirectory(wchar_t *buffer, DWORD count) {
    DWORD length = GetModuleFileNameW(NULL, buffer, count);
    if (length == 0 || length >= count) return FALSE;
    wchar_t *slash = wcsrchr(buffer, L'\\');
    if (!slash) return FALSE;
    *slash = L'\0';
    return TRUE;
}

static BOOL readUtf8File(const wchar_t *path, wchar_t *output, DWORD outputCount) {
    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return FALSE;
    DWORD size = GetFileSize(file, NULL);
    if (size == INVALID_FILE_SIZE || size == 0 || size > 64 * 1024) {
        CloseHandle(file);
        return FALSE;
    }
    char *bytes = (char *)HeapAlloc(GetProcessHeap(), 0, size + 1);
    if (!bytes) {
        CloseHandle(file);
        return FALSE;
    }
    DWORD read = 0;
    BOOL ok = ReadFile(file, bytes, size, &read, NULL);
    CloseHandle(file);
    if (!ok) {
        HeapFree(GetProcessHeap(), 0, bytes);
        return FALSE;
    }
    int converted = MultiByteToWideChar(CP_UTF8, 0, bytes, (int)read,
        output, (int)outputCount - 1);
    HeapFree(GetProcessHeap(), 0, bytes);
    if (converted <= 0) return FALSE;
    output[converted] = L'\0';
    return TRUE;
}

static DWORD WINAPI installWorker(LPVOID parameter) {
    InstallRequest *request = (InstallRequest *)parameter;
    InstallResult *result = (InstallResult *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY,
        sizeof(InstallResult));
    if (!result) {
        HeapFree(GetProcessHeap(), 0, request);
        return 1;
    }
    wchar_t baseDirectory[MAX_PATH], temporaryDirectory[MAX_PATH], statusPath[MAX_PATH];
    wchar_t systemDirectory[MAX_PATH], powershell[MAX_PATH], script[MAX_PATH];
    wchar_t commandLine[4096];
    if (!getModuleDirectory(baseDirectory, MAX_PATH)
        || !GetTempPathW(MAX_PATH, temporaryDirectory)
        || !GetTempFileNameW(temporaryDirectory, L"vnr", 0, statusPath)
        || !GetSystemDirectoryW(systemDirectory, MAX_PATH)) {
        wcscpy_s(result->message, 1024, L"Could not prepare the installation process.");
        PostMessageW(request->window, WM_INSTALL_COMPLETE, 0, (LPARAM)result);
        HeapFree(GetProcessHeap(), 0, request);
        return 1;
    }
    DeleteFileW(statusPath);
    _snwprintf_s(powershell, MAX_PATH, _TRUNCATE,
        L"%ls\\WindowsPowerShell\\v1.0\\powershell.exe", systemDirectory);
    _snwprintf_s(script, MAX_PATH, _TRUNCATE, L"%ls\\install.ps1", baseDirectory);
    if (request->gamePath[0] != L'\0') {
        _snwprintf_s(commandLine, 4096, _TRUNCATE,
            L"\"%ls\" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File \"%ls\" -BaseDirectory \"%ls\" -RuntimeCode \"%ls\" -StatusFile \"%ls\" -GamePath \"%ls\"",
            powershell, script, baseDirectory, request->runtimeCode, statusPath, request->gamePath);
    } else {
        _snwprintf_s(commandLine, 4096, _TRUNCATE,
            L"\"%ls\" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File \"%ls\" -BaseDirectory \"%ls\" -RuntimeCode \"%ls\" -StatusFile \"%ls\"",
            powershell, script, baseDirectory, request->runtimeCode, statusPath);
    }

    STARTUPINFOW startup = {0};
    PROCESS_INFORMATION process = {0};
    startup.cb = sizeof(startup);
    BOOL created = CreateProcessW(NULL, commandLine, NULL, NULL, FALSE,
        CREATE_NO_WINDOW, NULL, baseDirectory, &startup, &process);
    if (!created) {
        wcscpy_s(result->message, 1024, L"Could not start Windows PowerShell.");
    } else {
        WaitForSingleObject(process.hProcess, INFINITE);
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
        wchar_t status[2048];
        if (!readUtf8File(statusPath, status, 2048)) {
            wcscpy_s(result->message, 1024, L"The installer ended without a status report.");
        } else if (wcsncmp(status, L"SUCCESS\n", 8) == 0) {
            result->success = TRUE;
            wcscpy_s(result->message, 1024,
                L"Localization installed. You can launch the game now.");
        } else if (wcsncmp(status, L"ERROR\n", 6) == 0) {
            wcsncpy_s(result->message, 1024, status + 6, _TRUNCATE);
        } else {
            wcsncpy_s(result->message, 1024, status, _TRUNCATE);
        }
    }
    DeleteFileW(statusPath);
    PostMessageW(request->window, WM_INSTALL_COMPLETE, 0, (LPARAM)result);
    HeapFree(GetProcessHeap(), 0, request);
    return 0;
}

static void beginInstall(HWND window) {
    int selection = (int)SendMessageW(languageCombo, CB_GETCURSEL, 0, 0);
    if (selection < 0 || selection >= (int)(sizeof(runtimeCodes) / sizeof(runtimeCodes[0]))) return;
    InstallRequest *request = (InstallRequest *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY,
        sizeof(InstallRequest));
    if (!request) return;
    request->window = window;
    wcsncpy_s(request->runtimeCode, 16, runtimeCodes[selection], _TRUNCATE);
    wcsncpy_s(request->gamePath, MAX_PATH, selectedGamePath, _TRUNCATE);
    HANDLE thread = CreateThread(NULL, 0, installWorker, request, 0, NULL);
    if (!thread) {
        HeapFree(GetProcessHeap(), 0, request);
        installState = STATE_ERROR;
        wcscpy_s(statusMessage, 1024, L"Could not start the installation worker.");
        InvalidateRect(window, NULL, FALSE);
        return;
    }
    CloseHandle(thread);
    installState = STATE_WORKING;
    wcscpy_s(statusMessage, 1024,
        L"Verifying and installing the selected localization…");
    EnableWindow(languageCombo, FALSE);
    EnableWindow(chooseGameButton, FALSE);
    EnableWindow(installButton, FALSE);
    ShowWindow(progressBar, SW_SHOW);
    SendMessageW(progressBar, PBM_SETMARQUEE, TRUE, 30);
    InvalidateRect(window, NULL, FALSE);
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
                450, 310, 218, 44, window, (HMENU)ID_INSTALL, NULL, NULL);
            setFont(installButton, bodyFont);
            chooseGameButton = CreateWindowW(L"BUTTON", L"Game folder…",
                WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_OWNERDRAW,
                320, 310, 116, 44, window, (HMENU)ID_CHOOSE_GAME, NULL, NULL);
            setFont(chooseGameButton, smallFont);
            progressBar = CreateWindowExW(0, PROGRESS_CLASSW, NULL,
                WS_CHILD | PBS_MARQUEE | PBS_SMOOTH,
                320, 352, 348, 7, window, (HMENU)ID_PROGRESS, NULL, NULL);
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
            if ((UINT)wParam == ID_CHOOSE_GAME) {
                drawSecondaryButton((const DRAWITEMSTRUCT *)lParam);
                return TRUE;
            }
            break;
        case WM_COMMAND:
            if (LOWORD(wParam) == ID_LANGUAGE && HIWORD(wParam) == CBN_SELCHANGE
                && installState != STATE_WORKING) {
                installState = STATE_READY;
                wcscpy_s(statusMessage, 1024, L"Ready to install.");
                InvalidateRect(window, NULL, FALSE);
                return 0;
            }
            if (LOWORD(wParam) == ID_INSTALL) {
                if (installState == STATE_SUCCESS) {
                    if ((INT_PTR)ShellExecuteW(window, L"open", L"steam://rungameid/2324650",
                        NULL, NULL, SW_SHOWNORMAL) <= 32) {
                        installState = STATE_ERROR;
                        wcscpy_s(statusMessage, 1024,
                            L"Could not open Steam. Launch the game from your Steam library.");
                        InvalidateRect(window, NULL, FALSE);
                    }
                } else if (installState != STATE_WORKING) {
                    beginInstall(window);
                }
                return 0;
            }
            if (LOWORD(wParam) == ID_CHOOSE_GAME && installState != STATE_WORKING) {
                chooseGameFolder(window);
                return 0;
            }
            break;
        case WM_INSTALL_COMPLETE: {
            InstallResult *result = (InstallResult *)lParam;
            SendMessageW(progressBar, PBM_SETMARQUEE, FALSE, 0);
            ShowWindow(progressBar, SW_HIDE);
            EnableWindow(languageCombo, TRUE);
            EnableWindow(chooseGameButton, TRUE);
            EnableWindow(installButton, TRUE);
            installState = result->success ? STATE_SUCCESS : STATE_ERROR;
            wcsncpy_s(statusMessage, 1024, result->message, _TRUNCATE);
            HeapFree(GetProcessHeap(), 0, result);
            InvalidateRect(window, NULL, FALSE);
            SetFocus(installButton);
            return 0;
        }
        case WM_CLOSE:
            if (installState == STATE_WORKING) {
                MessageBeep(MB_ICONINFORMATION);
                wcscpy_s(statusMessage, 1024,
                    L"Installation is in progress. Keep this window open until it finishes.");
                InvalidateRect(window, NULL, FALSE);
                return 0;
            }
            DestroyWindow(window);
            return 0;
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
    INITCOMMONCONTROLSEX controls = { sizeof(controls), ICC_STANDARD_CLASSES | ICC_PROGRESS_CLASS };
    InitCommonControlsEx(&controls);
    interactiveWindowStation = OpenWindowStationW(L"WinSta0", FALSE, WINSTA_ALL_ACCESS);
    if (interactiveWindowStation) {
        SetProcessWindowStation(interactiveWindowStation);
        interactiveDesktop = OpenDesktopW(L"Default", 0, FALSE, MAXIMUM_ALLOWED);
        if (interactiveDesktop) SetThreadDesktop(interactiveDesktop);
    }
    HRESULT oleResult = OleInitialize(NULL);
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
        CW_USEDEFAULT, CW_USEDEFAULT, 760, 555, NULL, NULL, instance, NULL);
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
    if (SUCCEEDED(oleResult)) OleUninitialize();
    return (int)message.wParam;
}
