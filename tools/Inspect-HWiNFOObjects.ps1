$ErrorActionPreference='Stop'
Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public class ObjectDirectories {
 [StructLayout(LayoutKind.Sequential)] struct US { public ushort Length,Max; public IntPtr Buffer; }
 [StructLayout(LayoutKind.Sequential)] struct OA { public int Length; public IntPtr Root,Name; public uint Attributes; public IntPtr SD,SQ; }
 [StructLayout(LayoutKind.Sequential)] struct ENTRY { public US Name,Type; }
 [DllImport("ntdll.dll")] static extern int NtOpenDirectoryObject(out IntPtr h,uint access,ref OA oa);
 [DllImport("ntdll.dll")] static extern int NtQueryDirectoryObject(IntPtr h,IntPtr b,uint len,bool single,bool restart,ref uint context,out uint returned);
 [DllImport("ntdll.dll")] static extern int NtClose(IntPtr h);
 public static string[] List(string path) {
  IntPtr txt=Marshal.StringToHGlobalUni(path), up=Marshal.AllocHGlobal(Marshal.SizeOf<US>()),buf=Marshal.AllocHGlobal(65536),h=IntPtr.Zero;
  var result=new List<string>();
  try { var us=new US{Length=(ushort)(path.Length*2),Max=(ushort)(path.Length*2+2),Buffer=txt}; Marshal.StructureToPtr(us,up,false);
   var oa=new OA{Length=Marshal.SizeOf<OA>(),Name=up,Attributes=64}; int st=NtOpenDirectoryObject(out h,1,ref oa); if(st<0) return new[]{"OPEN_STATUS="+st.ToString("X8")};
   uint ctx=0,ret; bool first=true;
   while((st=NtQueryDirectoryObject(h,buf,65536,true,first,ref ctx,out ret))>=0) { first=false; var e=Marshal.PtrToStructure<ENTRY>(buf); string name=Marshal.PtrToStringUni(e.Name.Buffer,e.Name.Length/2); string type=Marshal.PtrToStringUni(e.Type.Buffer,e.Type.Length/2); if(name.IndexOf("hwinfo",StringComparison.OrdinalIgnoreCase)>=0 || name.IndexOf("sens",StringComparison.OrdinalIgnoreCase)>=0) result.Add(type+" "+name); }
   result.Add("END_STATUS="+st.ToString("X8")); return result.ToArray();
  } finally { if(h!=IntPtr.Zero) NtClose(h); Marshal.FreeHGlobal(buf); Marshal.FreeHGlobal(up); Marshal.FreeHGlobal(txt); }
 }
}
"@
foreach($path in @('\BaseNamedObjects','\Sessions\1\BaseNamedObjects','\Sessions\0\BaseNamedObjects')) {
 [ordered]@{path=$path;objects=[ObjectDirectories]::List($path)} | ConvertTo-Json -Depth 3
}
Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'hwtrace|hwinfo'} | Select-Object Name,ProcessId,SessionId,CreationDate | ConvertTo-Json
