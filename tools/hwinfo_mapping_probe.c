#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
int main(void) {
 const wchar_t *names[]={L"Global\\HWiNFO_SENS_SM2",L"Local\\HWiNFO_SENS_SM2"};
 int found=0;
 for(unsigned i=0;i<2;i++){
  HANDLE h=OpenFileMappingW(FILE_MAP_READ,FALSE,names[i]);
  if(!h){printf("%s: OpenFileMappingW failed Win32=%lu\n",i?"Local":"Global",GetLastError());continue;}
  const unsigned char *p=MapViewOfFile(h,FILE_MAP_READ,0,0,0);MEMORY_BASIC_INFORMATION m;
  if(!p)printf("%s: MapViewOfFile failed Win32=%lu\n",i?"Local":"Global",GetLastError());
  else {if(VirtualQuery(p,&m,sizeof m))printf("%s: mapped bytes=%llu magic=%02x%02x%02x%02x\n",i?"Local":"Global",(unsigned long long)m.RegionSize,p[0],p[1],p[2],p[3]);UnmapViewOfFile(p);found=1;}
  CloseHandle(h);
 }
 return found?0:1;
}
