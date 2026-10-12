import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

type Turn = { id:number; code:string; customer_name:string; service:string; priority:number; status:string; counter:number|null; created_at:string; appointment_at:string|null };
type Counter = { id:number; name:string; active:number; turn:Turn|null };
type Stats = { total:number; waiting:number; serving:number; completed:number };

@Component({ selector:'app-root', standalone:true, imports:[CommonModule,FormsModule], templateUrl:'./app.component.html' })
export class AppComponent implements OnInit {
  private api='http://localhost:8000/api';
  turns:Turn[]=[]; counters:Counter[]=[]; stats:Stats={total:0,waiting:0,serving:0,completed:0};
  services=['Depósitos','Retiros','Aclaraciones','Pagos','Atención preferente'];
  name=''; service=this.services[0]; priority=false; appointmentMode=false; appointment=''; notice=''; busy=false;
  nowLabel=new Intl.DateTimeFormat('es-MX',{weekday:'long',day:'numeric',month:'long'}).format(new Date());
  constructor(private http:HttpClient){}
  ngOnInit(){this.refresh();setInterval(()=>this.refresh(),10000);}
  refresh(){this.http.get<Turn[]>(`${this.api}/turns`).subscribe({next:x=>this.turns=x,error:()=>this.notice='No se pudo conectar con el backend.'});this.http.get<Counter[]>(`${this.api}/counters`).subscribe(x=>this.counters=x);this.http.get<Stats>(`${this.api}/stats`).subscribe(x=>this.stats=x);}
  issue(){if(!this.name.trim())return;this.busy=true;const body:any={customer_name:this.name,service:this.service,priority:this.priority};if(this.appointmentMode&&this.appointment)body.appointment_at=new Date(this.appointment).toISOString();this.http.post<Turn>(`${this.api}/turns`,body).subscribe({next:t=>{this.notice=`Turno ${t.code} asignado a ${t.customer_name}.`;this.name='';this.appointment='';this.priority=false;this.busy=false;this.refresh();},error:e=>{this.notice=e.error?.detail||'No se pudo emitir el turno.';this.busy=false;}});}
  callNext(c:Counter){this.http.post<any>(`${this.api}/counters/${c.id}/next`,{}).subscribe({next:r=>{this.notice=r.turn?`${r.turn.code} llamado a ${c.name}.`:r.message;this.refresh();},error:e=>this.notice=e.error?.detail||'No se pudo llamar el turno.'});}
  start(t:Turn){this.http.post(`${this.api}/turns/${t.id}/start`,{}).subscribe({next:()=>this.refresh(),error:e=>this.notice=e.error?.detail||'No se pudo iniciar la atención.'});}
  complete(t:Turn){this.http.post(`${this.api}/turns/${t.id}/complete`,{}).subscribe({next:()=>{this.notice=`Atención de ${t.code} finalizada.`;this.refresh();},error:e=>this.notice=e.error?.detail||'No se pudo cerrar el turno.'});}
  toggle(c:Counter){this.http.patch(`${this.api}/counters/${c.id}`,{active:!c.active}).subscribe(()=>this.refresh());}
  statusLabel(s:string){return ({waiting:'En espera',called:'Llamado',in_service:'En atención',completed:'Atendido',scheduled:'Cita'} as any)[s]||s;}
  get minDate(){return new Date(Date.now()+60000).toISOString().slice(0,16)}
  get maxDate(){return new Date(Date.now()+122*86400000).toISOString().slice(0,16)}
}

