struct VPNItem {
   1: string status,
   2: string ip,
   3: string description
 }

 struct VPNResult {
   1: string code,
   2: string msg,
   3: list<VPNItem> data
 }

 service VPNRPCService{
     VPNResult synchronize(1:string type, 2:string ip, 3:map<string,string> policy),
     VPNResult query(1:string ip)
 }

