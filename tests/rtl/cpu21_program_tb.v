`timescale 1ns/1ps
// Original CPU RTL, board-equivalent Harvard memories. All files stay local.
module cpu21_program_tb;
  reg clk=0; always #5 clk=~clk;
  reg reset=1;
  reg [31:0] rom[0:8191];
  reg [31:0] ram[0:1023];
  reg [31:0] fb[0:599];
  wire [31:0] pc,addr,wdata,led,seg,disp_ctrl,disp_cursor,ustatus;
  wire [3:0] strb,fb_strb;
  wire we,led_valid,seg_valid,fb_we;
  wire [9:0] fb_addr;
  wire [31:0] fb_data;
  wire [31:0] instr=rom[pc[14:2]];
  wire [31:0] rdata=(addr<4096)?ram[addr[11:2]]:0;
  reg [4095:0] filename,fbfile;
  integer i,cycles=0;
  reg seen_led=0;
  wire [2:0] irq=(cycles>200 && cycles<210)?3'b111:3'b000;
  cpu21_riscv_redirect_int_bpb dut(
    .clk(clk),.reset(reset),.instr_i(instr),.data_rdata_i(rdata),
    .irq_i(irq),.go_i(1'b0),.instr_addr_o(pc),.data_addr_o(addr),
    .data_wdata_o(wdata),.data_wstrb_o(strb),.data_we_o(we),
    .led_data_o(led),.led_valid_o(led_valid),.seg_data_o(seg),.seg_valid_o(seg_valid),
    .fb_we_o(fb_we),.fb_waddr_o(fb_addr),.fb_wdata_o(fb_data),.fb_wstrb_o(fb_strb),
    .fb_rdata_i(fb[0]),.disp_ctrl_o(disp_ctrl),.disp_cursor_o(disp_cursor),.ustatus_o(ustatus),
    .mouse_ev_valid_i(1'b0),.mouse_dx_i(8'b0),.mouse_dy_i(8'b0),
    .mouse_btn_i(5'b0),.sw_i(16'b0),.frame_tick_i(1'b0));
  initial begin
    if(!$value$plusargs("ROM=%s",filename))$fatal(1,"ROM argument missing");
    if(!$value$plusargs("FB=%s",fbfile))$fatal(1,"FB argument missing");
    for(i=0;i<1024;i=i+1)ram[i]=32'ha5a5a5a5;
    for(i=0;i<600;i=i+1)fb[i]=32'hdeadbeef;
    for(i=0;i<8192;i=i+1)rom[i]=32'h00000013;
    $readmemh(filename,rom);
    #42 reset=0;
  end
  always @(posedge clk) if(!reset)begin
    cycles=cycles+1;
    if(cycles==100 && ustatus[0]!==1'b0)$fatal(1,"interrupts not disabled");
    if(pc>=32768)$fatal(1,"PC outside ROM: %08x",pc);
    if(we && addr<4096)begin
      if(strb[0])ram[addr[11:2]][7:0]<=wdata[7:0];
      if(strb[1])ram[addr[11:2]][15:8]<=wdata[15:8];
      if(strb[2])ram[addr[11:2]][23:16]<=wdata[23:16];
      if(strb[3])ram[addr[11:2]][31:24]<=wdata[31:24];
    end
    if(fb_we)begin
      if(fb_strb[0])fb[fb_addr][7:0]<=fb_data[7:0];
      if(fb_strb[1])fb[fb_addr][15:8]<=fb_data[15:8];
      if(fb_strb[2])fb[fb_addr][23:16]<=fb_data[23:16];
      if(fb_strb[3])fb[fb_addr][31:24]<=fb_data[31:24];
    end
    if(we && addr>=4096 && !(addr==32'h1000 || addr==32'h1004 ||
        addr==32'h110c || addr==32'h1140 || addr==32'h1144 ||
        (addr>=32'h2000 && addr<32'h2960)))
      $fatal(1,"store outside RAM/MMIO: %08x",addr);
    if(led_valid)seen_led=1;
    if(seg_valid && seen_led)begin
      if(led!==seg)$fatal(1,"LED/SEG exit status mismatch");
      $writememh(fbfile,fb);
      $display("CPU21_RESULT=%0d CYCLES=%0d CURSOR=%08x CTRL=%08x",led,cycles,disp_cursor,disp_ctrl);
      $finish;
    end
    if(cycles>2000000)$fatal(1,"program timeout pc=%08x",pc);
  end
endmodule
