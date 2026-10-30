#define _CRT_SECURE_NO_WARNINGS
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdarg.h>
#include <string.h>
#include <math.h>
#include <time.h>

#define QSIZE 128
#define LINE 65536
#define MAXPAT 128
static char queue[QSIZE][LINE];
static unsigned head, count, dropped; static CRITICAL_SECTION lock;
static volatile LONG stopping; static char session[64]; static unsigned seq;
static char patterns[MAXPAT][128]; static int npat; static char process_name[128] = "TM5.exe";
static unsigned grace_ms=600000; static char ssh_command[4096];
static HANDLE input_write, output_read, child; static volatile LONG child_running;
static char linebuf[LINE]; static size_t used;
static char marker[1024];
static char source_error[256] = "No snapshot attempted";

static void append(const char *fmt, ...) { va_list a; int n; if (used >= LINE-1) return; va_start(a,fmt); n=vsnprintf(linebuf+used,LINE-used,fmt,a); va_end(a); if(n<0 || (size_t)n>=LINE-used) used=LINE; else used+=(size_t)n; }
static void jsonstr(const char *s) { const unsigned char *p=(const unsigned char*)s; append("\""); for(;*p;p++) { if(*p=='"'||*p=='\\') append("\\%c",*p); else if(*p<32) append("\\u%04x",*p); else append("%c",*p); } append("\""); }
static void begin(const char *kind) { SYSTEMTIME t; GetSystemTime(&t); used=0; append("{\"version\":1,\"session\":\"%s\",\"seq\":%u,\"timestamp\":\"%04u-%02u-%02uT%02u:%02u:%02u.%03uZ\",\"kind\":\"%s\"", session,seq++,t.wYear,t.wMonth,t.wDay,t.wHour,t.wMinute,t.wSecond,t.wMilliseconds,kind); }
static int enqueue(void) { int ok=0; if(used>=LINE-2) { fprintf(stderr,"record too large\n"); return 0; } append("}\n"); EnterCriticalSection(&lock); if(count<QSIZE) { memcpy(queue[(head+count)%QSIZE],linebuf,used+1); count++; ok=1; } else dropped++; LeaveCriticalSection(&lock); return ok; }
static void event(const char *name,const char *detail) { begin("event"); append(",\"event\":"); jsonstr(name); append(",\"detail\":"); jsonstr(detail); enqueue(); }
static int start_ssh(void) {
 SECURITY_ATTRIBUTES sa={sizeof(sa),NULL,TRUE}; HANDLE rd,wr; STARTUPINFOA si={0}; PROCESS_INFORMATION pi={0}; char cmd[sizeof ssh_command];
 if(!CreatePipe(&rd,&input_write,&sa,0)) return 0;
 if(!CreatePipe(&output_read,&wr,&sa,0)) { CloseHandle(rd); CloseHandle(input_write); return 0; }
 SetHandleInformation(input_write,HANDLE_FLAG_INHERIT,0); SetHandleInformation(output_read,HANDLE_FLAG_INHERIT,0);
 si.cb=sizeof(si); si.dwFlags=STARTF_USESTDHANDLES; si.hStdInput=rd; si.hStdOutput=wr; si.hStdError=GetStdHandle(STD_ERROR_HANDLE); strcpy(cmd,ssh_command);
 if(!CreateProcessA(NULL,cmd,NULL,NULL,TRUE,CREATE_NO_WINDOW,NULL,NULL,&si,&pi)) { CloseHandle(rd); CloseHandle(wr); CloseHandle(input_write); CloseHandle(output_read); return 0; }
 CloseHandle(rd); CloseHandle(wr); CloseHandle(pi.hThread); child=pi.hProcess; InterlockedExchange(&child_running,1); return 1;
}
static void stop_ssh(void) { if(child) { CloseHandle(input_write); CloseHandle(output_read); if(WaitForSingleObject(child,1500)==WAIT_TIMEOUT) TerminateProcess(child,1); CloseHandle(child); child=NULL; InterlockedExchange(&child_running,0); } }
static int read_ack(void) { char ack[3]; DWORD n, total=0; while(total<3) { if(!ReadFile(output_read,ack+total,3-total,&n,NULL) || !n) return 0; total+=n; } return memcmp(ack,"OK\n",3)==0; }
static DWORD WINAPI sender(void *unused) { char buf[LINE]; DWORD wrote; (void)unused; while(!stopping || count) { int have=0; EnterCriticalSection(&lock); if(count) { strcpy(buf,queue[head]); have=1; } LeaveCriticalSection(&lock); if(!have) { Sleep(25); continue; } if(!child && !start_ssh()) { Sleep(1000); continue; } if(WaitForSingleObject(child,0)==WAIT_OBJECT_0 || !WriteFile(input_write,buf,(DWORD)strlen(buf),&wrote,NULL) || wrote!=strlen(buf) || !read_ack()) { stop_ssh(); Sleep(1000); continue; } EnterCriticalSection(&lock); head=(head+1)%QSIZE; count--; LeaveCriticalSection(&lock); } stop_ssh(); return 0; }
static uint32_t u32(const unsigned char *p) { uint32_t v; memcpy(&v,p,4); return v; }
static double f64(const unsigned char *p) { double v; memcpy(&v,p,8); return v; }
static void strfield_codepage(char *out, size_t cap, const unsigned char *p, int n, UINT codepage) { char ansi[129], utf8[512]; int len=0; while(len<n && p[len]) { ansi[len]=(char)p[len]; len++; } ansi[len]=0; { WCHAR w[129]; int wn=MultiByteToWideChar(codepage,0,ansi,-1,w,129); if(!wn || !WideCharToMultiByte(CP_UTF8,0,w,-1,utf8,sizeof utf8,NULL,NULL)) utf8[0]=0; } snprintf(out,cap,"%s",utf8); }
static void strfield(char *out, size_t cap, const unsigned char *p, int n) { strfield_codepage(out,cap,p,n,CP_ACP); }
/* Legacy HWiNFO unit fields use Western ANSI bytes (e.g. B0 43 for degree C), independent of the Windows UI code page. */
static void unitfield(char *out, size_t cap, const unsigned char *p) { strfield_codepage(out,cap,p,16,1252); }
static int contains_ci(const char *haystack,const char *needle) { size_t n=strlen(needle); const char *p; if(!n) return 1; for(p=haystack;*p;p++) if(!_strnicmp(p,needle,n)) return 1; return 0; }
static int selected(const char *sensor,const char *name) { int i; if(!npat) return 1; for(i=0;i<npat;i++) { const char *bar=strchr(patterns[i],'|'); if(bar) { char prefix[128]; size_t n=(size_t)(bar-patterns[i]); memcpy(prefix,patterns[i],n); prefix[n]=0; if(contains_ci(sensor,prefix) && contains_ci(name,bar+1)) return 1; } else if(contains_ci(name,patterns[i])) return 1; } return 0; }
static int is_running(void) { PROCESSENTRY32 p; HANDLE h=CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS,0); int found=0; if(h==INVALID_HANDLE_VALUE) return -1; p.dwSize=sizeof(p); if(Process32First(h,&p)) do { if(!_stricmp(p.szExeFile,process_name)) { found=1; break; } } while(Process32Next(h,&p)); CloseHandle(h); return found; }
static DWORD WINAPI keyboard(void *unused) {
    char text[1024]; (void)unused;
    while(fgets(text,sizeof text,stdin)) {
        text[strcspn(text,"\r\n")]=0;
        if(*text) { EnterCriticalSection(&lock); if(!*marker) strcpy(marker,text); else fprintf(stderr,"marker mailbox full\n"); LeaveCriticalSection(&lock); }
    }
    return 0;
}
static unsigned char *snapshot(size_t *len) {
    HANDLE h; void *p; MEMORY_BASIC_INFORMATION mbi; unsigned char *b=NULL;
    h=OpenFileMappingW(FILE_MAP_READ,FALSE,L"Global\\HWiNFO_SENS_SM2");
    if(!h) { snprintf(source_error,sizeof source_error,"OpenFileMappingW(Global\\HWiNFO_SENS_SM2) failed: Win32=%lu",GetLastError()); return NULL; }
    p=MapViewOfFile(h,FILE_MAP_READ,0,0,0);
    if(!p) snprintf(source_error,sizeof source_error,"MapViewOfFile failed: Win32=%lu",GetLastError());
    else if(!VirtualQuery(p,&mbi,sizeof mbi)) snprintf(source_error,sizeof source_error,"VirtualQuery failed: Win32=%lu",GetLastError());
    else if(mbi.RegionSize<48 || mbi.RegionSize>64*1024*1024) snprintf(source_error,sizeof source_error,"Invalid mapping region size: %llu",(unsigned long long)mbi.RegionSize);
    else {
        *len=mbi.RegionSize; b=malloc(*len);
        if(b) memcpy(b,p,*len);
        else snprintf(source_error,sizeof source_error,"Snapshot allocation failed: %llu bytes",(unsigned long long)*len);
    }
    if(p) UnmapViewOfFile(p);
    CloseHandle(h);
    return b;
}
static int serialize_sensor(int metadata, const unsigned char *b, size_t len) { uint32_t so,ss,sc,eo,es,ec,i; int found=0; if(!b) return -1; so=u32(b+20); ss=u32(b+24); sc=u32(b+28); eo=u32(b+32); es=u32(b+36); ec=u32(b+40); if(u32(b)!=0x53695748 || so<48 || eo<48 || ss<264 || es<316 || sc>4096 || ec>65536 || (uint64_t)so+(uint64_t)ss*sc>len || (uint64_t)eo+(uint64_t)es*ec>len || (so<(uint64_t)eo+(uint64_t)es*ec && eo<(uint64_t)so+(uint64_t)ss*sc)) { snprintf(source_error,sizeof source_error,"Malformed HWiNFO header: magic=%08x sensors=%u entries=%u",u32(b),sc,ec); return -1; }
 begin(metadata?"metadata":"sample"); append(metadata?",\"sensors\":[":",\"values\":[");
 for(i=0;i<ec;i++) { const unsigned char *e=b+eo+(size_t)i*es,*s; uint32_t idx=u32(e+4); char sn[512],rn[512],unit[100]; double v; if(idx>=sc) continue; s=b+so+(size_t)idx*ss; strfield(sn,sizeof sn,s+136,128); if(!*sn) strfield(sn,sizeof sn,s+8,128); strfield(rn,sizeof rn,e+140,128); if(!*rn) strfield(rn,sizeof rn,e+12,128); unitfield(unit,sizeof unit,e+268); v=f64(e+284); if(!selected(sn,rn) || (!metadata && !isfinite(v))) continue; if(found++) append(","); append("{\"sensor_id\":%u,\"sensor_instance\":%u,\"reading_id\":%u",u32(s),u32(s+4),u32(e+8)); if(metadata) { append(",\"sensor_name\":"); jsonstr(sn); append(",\"reading_name\":"); jsonstr(rn); append(",\"unit\":"); jsonstr(unit); append(",\"reading_type\":%u",u32(e)); } else append(",\"value\":%.17g",v); append("}"); }
 append("]"); if(!enqueue()) { snprintf(source_error,sizeof source_error,"Output record too large or ring buffer full"); return -1; } return found; }
static int read_cycle(int with_sample) {
    size_t len=0;
    unsigned char *b=snapshot(&len);
    if(!b) return -1;
    /* Metadata includes non-finite readings and both records use the same snapshot.
       A newly valid sample must never arrive before its sensor metadata. */
    int result=serialize_sensor(1,b,len);
    if(result>=0 && with_sample) result=serialize_sensor(0,b,len);
    free(b);
    return result;
}
static BOOL WINAPI control(DWORD code) { if(code==CTRL_C_EVENT||code==CTRL_BREAK_EVENT||code==CTRL_CLOSE_EVENT) { InterlockedExchange(&stopping,1); return TRUE; } return FALSE; }
int main(int argc,char **argv) { FILE *f; char buf[256]; HANDLE thread; int seen=0,was=0,metadata=0,missing=0; ULONGLONG deadline=0,next=0; if(argc>=2 && !strcmp(argv[1],"--diagnose")) {
    size_t bytes=0; unsigned char *b=snapshot(&bytes);
    if(!b) { fprintf(stderr,"%s\n",source_error); return 1; }
    printf("HWiNFO shared memory: bytes=%llu magic=%08x version=%u sensors=%u readings=%u\n",(unsigned long long)bytes,u32(b),u32(b+4),u32(b+28),u32(b+40));
    if(argc>2) {
        FILE *df=fopen(argv[2],"r"); char pat[256];
        if(!df) { free(b); perror("filter"); return 2; }
        while(fgets(pat,sizeof pat,df)) { pat[strcspn(pat,"\r\n")]=0; if(*pat && *pat!='#' && npat<MAXPAT) snprintf(patterns[npat++],sizeof patterns[0],"%.127s",pat); }
        fclose(df);
        uint32_t eo=u32(b+32),es=u32(b+36),ec=u32(b+40),sc=u32(b+28); int matches=0;
        if(es<316 || (uint64_t)eo+(uint64_t)es*ec>bytes) { free(b); return 1; }
        printf("filter patterns=%d first=%s\n",npat,npat?patterns[0]:"(all)");
        for(uint32_t i=0;i<ec;i++) { const unsigned char *e=b+eo+(size_t)i*es; char name[512]; double v=f64(e+284); strfield(name,sizeof name,e+140,128); if(!*name)strfield(name,sizeof name,e+12,128);
            int match=selected("",name); if(match && isfinite(v) && u32(e+4)<sc)matches++;
            if(i<8)printf("entry=%u sensor_idx=%u name=%s value=%.5g finite=%d match=%d\n",i,u32(e+4),name,v,!!isfinite(v),match);
        }
        printf("selected=%d (sensor-qualified rules excluded from this probe)\n",matches);
    }
    free(b); return 0;
} if(argc<3) { fprintf(stderr,"usage: hwtrace.exe filter.txt \"ssh command\" [process.exe] [grace_seconds]\n"); return 2; } f=fopen(argv[1],"r"); if(!f) { perror("filter"); return 2; } while(fgets(buf,sizeof buf,f)) { size_t n=strcspn(buf,"\r\n"); buf[n]=0; if(*buf && *buf!='#' && npat<MAXPAT) snprintf(patterns[npat++],sizeof patterns[0],"%.127s",buf); } fclose(f); if(strlen(argv[2])>=sizeof ssh_command) return 2; strcpy(ssh_command,argv[2]); if(argc>3) snprintf(process_name,sizeof process_name,"%s",argv[3]); if(argc>4) grace_ms=(unsigned)(strtoul(argv[4],NULL,10)*1000); snprintf(session,sizeof session,"%08lx-%08lx-%016llx",GetCurrentProcessId(),GetTickCount(),(unsigned long long)time(NULL)); InitializeCriticalSection(&lock); SetConsoleCtrlHandler(control,TRUE); thread=CreateThread(NULL,0,sender,NULL,0,NULL); CloseHandle(CreateThread(NULL,0,keyboard,NULL,0,NULL)); event("collector_start",process_name); fprintf(stderr,"HWTrace started. Ctrl+C stops.\n");
 while(!stopping) { ULONGLONG now=GetTickCount64(); int running,n; if(now<next) { Sleep((DWORD)(next-now)); continue; } next=now+500; { char msg[1024]; EnterCriticalSection(&lock); strcpy(msg,marker); marker[0]=0; LeaveCriticalSection(&lock); if(*msg) event("marker",msg); } running=is_running(); if(running>=0) { if(running&&!was) { event("process_start",process_name); seen=1; deadline=0; } if(!running&&was) { event("process_exit",process_name); deadline=now+grace_ms; } was=running; if(seen && !running && deadline && now>=deadline) { event("auto_stop",process_name); break; } }
 if(!metadata) { n=read_cycle(0); if(n>=0) { metadata=1; fprintf(stderr,"selected %d readings\n",n); if(missing) event("source_restored","HWiNFO shared memory"); missing=0; } else if(!missing) { event("source_unavailable",source_error); fprintf(stderr,"%s\n",source_error); missing=1; } } else if(read_cycle(1)<0) { metadata=0; if(!missing) { event("source_unavailable",source_error); fprintf(stderr,"%s\n",source_error); missing=1; } } }
 event("collector_stop",""); InterlockedExchange(&stopping,1); if(WaitForSingleObject(thread,5000)==WAIT_TIMEOUT) { fprintf(stderr,"shutdown with pending records; dropped=%u\n",dropped); if(child_running) TerminateProcess(child,1); WaitForSingleObject(thread,2000); } fprintf(stderr,"dropped=%u pending=%u\n",dropped,count); return (dropped || count) ? 1 : 0; }

