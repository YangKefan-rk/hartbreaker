// See LICENSE.SiFive for license details.
//VCS coverage exclude_file
`ifndef RESET_DELAY
 `define RESET_DELAY 777.7
`endif
`ifndef MODEL
 `define MODEL TestHarness
`endif

module TestDriver;

  reg clock = 1'b0;
  reg reset = 1'b1;
  wire [15871:0] _auto_cover_out;
  // File descriptor and toggle-tracking registers for _auto_cover_out
  integer _auto_cover_out_fd = 0;
  // previous value of _auto_cover_out
  reg [15871:0] prev_auto_cover_out = {15872{1'b0}};
  // accumulated toggles (1 = bit toggled at least once)
  reg [15871:0] toggled_accum = {15872{1'b0}};
  // temporary per-cycle toggled bits
  logic [15871:0] toggled_tmp;
  assign toggled_tmp = prev_auto_cover_out ^ _auto_cover_out;

  always #(`CLOCK_PERIOD/2.0) clock = ~clock;
  initial #(`RESET_DELAY) reset = 0;

  // Read input arguments and initialize
  reg verbose = 1'b0;
  wire printf_cond = verbose && !reset;
  reg [63:0] max_cycles = 0;
  reg [63:0] dump_start = 0;
  reg [63:0] trace_count = 0;
  reg [2047:0] fsdbfile = 0;
  reg [2047:0] vcdplusfile = 0;
  reg [2047:0] vcdfile = 0;
  int unsigned rand_value;
  initial
  begin
    void'($value$plusargs("max-cycles=%d", max_cycles));
    void'($value$plusargs("dump-start=%d", dump_start));
    verbose = $test$plusargs("verbose");

    // do not delete the lines below.
    // $random function needs to be called with the seed once to affect all
    // the downstream $random functions within the Chisel-generated Verilog
    // code.
    // $urandom is seeded via cmdline (+ntb_random_seed in VCS) but that
    // doesn't seed $random.
    rand_value = $urandom;
    rand_value = $random(rand_value);
    if (verbose) begin
`ifdef VCS
      $fdisplay(stderr, "testing $random %0x seed %d", rand_value, unsigned'($get_initial_random_seed));
`else
      $fdisplay(stderr, "testing $random %0x", rand_value);
`endif
    end

`ifdef DEBUG

    if ($value$plusargs("vcdplusfile=%s", vcdplusfile))
    begin
`ifdef VCS
      $vcdplusfile(vcdplusfile);
`else
      $fdisplay(stderr, "Error: +vcdplusfile is VCS-only; use +vcdfile instead or recompile with VCS=1");
      $fatal;
`endif
    end

    if ($value$plusargs("fsdbfile=%s", fsdbfile))
    begin
`ifdef FSDB
      $fsdbDumpfile(fsdbfile);
      $fsdbDumpvars("+all");
      //$fsdbDumpSVA;
`else
      $fdisplay(stderr, "Error: +fsdbfile is FSDB-only; use +vcdfile/+vcdplus instead or recompile with FSDB=1");
      $fatal;
`endif
    end

    if ($value$plusargs("vcdfile=%s", vcdfile))
    begin
      $dumpfile(vcdfile);
      $dumpvars(0, testHarness);
    end

`ifdef FSDB
`define VCDPLUSON $fsdbDumpon;
`define VCDPLUSCLOSE $fsdbDumpoff;
`elsif VCS
`define VCDPLUSON $vcdpluson(0); $vcdplusmemon(0);
`define VCDPLUSCLOSE $vcdplusclose; $dumpoff;
`else
`define VCDPLUSON $dumpon;
`define VCDPLUSCLOSE $dumpoff;
`endif
`else
  // No +define+DEBUG
`define VCDPLUSON
`define VCDPLUSCLOSE

    if ($test$plusargs("vcdplusfile=") || $test$plusargs("vcdfile=") || $test$plusargs("fsdbfile="))
    begin
      $fdisplay(stderr, "Error: +vcdfile, +vcdplusfile, or +fsdbfile requested but compile did not have +define+DEBUG enabled");
      $fatal;
    end

`endif

    if (dump_start == 0)
    begin
      // Start dumping before first clock edge to capture reset sequence in waveform
      `VCDPLUSON
    end
  end

`ifdef TESTBENCH_IN_UVM
  // UVM library has its own way to manage end-of-simulation.
  // A UVM-based testbench will raise an objection, watch this signal until this goes 1, then drop the objection.
  reg finish_request = 1'b0;
`endif
// Open file to record toggled bits for _auto_cover_out
initial begin
  _auto_cover_out_fd = $fopen("auto_cover_toggled.out", "w");
  if (_auto_cover_out_fd == 0) begin
    $fdisplay(stderr, "Warning: could not open auto_cover_toggled.out for writing");
  end
end
  reg [255:0] reason = "";
  reg failure = 1'b0;
  wire success;
  integer stderr = 32'h80000002;
  always @(posedge clock)
  begin
`ifdef GATE_LEVEL
    if (verbose)
    begin
      $fdisplay(stderr, "C: %10d", trace_count);
    end
`endif

    trace_count = trace_count + 1;

  // --- toggle detection for _auto_cover_out ---
  // compute which bits toggled this cycle and accumulate
  toggled_accum <= toggled_accum | toggled_tmp;
  prev_auto_cover_out <= _auto_cover_out;

    if (trace_count == dump_start)
    begin
      `VCDPLUSON
    end

    if (!reset)
    begin
      if (max_cycles > 0 && trace_count > max_cycles)
      begin
        reason = " (timeout)";
        failure = 1'b1;
      end

      if (failure)
      begin
        $fdisplay(stderr, "*** FAILED ***%s after %d simulation cycles", reason, trace_count);
        // write toggled bits to file before aborting
        if (_auto_cover_out_fd != 0) begin
          $fwrite(_auto_cover_out_fd, "%b", toggled_accum[15871:8192]);
          $fdisplay(_auto_cover_out_fd, "%b", toggled_accum[8191:0]);
          $fclose(_auto_cover_out_fd);
        end
        `VCDPLUSCLOSE
        $fatal;
      end

      if (success)
      begin
        if (verbose)
          $fdisplay(stderr, "*** PASSED *** Completed after %d simulation cycles", trace_count);
        `VCDPLUSCLOSE
        // write toggled bits to file on successful completion
        if (_auto_cover_out_fd != 0) begin
          $fwrite(_auto_cover_out_fd, "%b", toggled_accum[15871:8192]);
          $fdisplay(_auto_cover_out_fd, "%b", toggled_accum[8191:0]);
          $fclose(_auto_cover_out_fd);
        end
`ifdef TESTBENCH_IN_UVM
        finish_request = 1;
`else
        $finish;
`endif
      end
    end
  end

  `MODEL testHarness(
    .clock(clock),
    .reset(reset),
    .io_success(success),
    .auto_cover_out(_auto_cover_out)
  );

endmodule
