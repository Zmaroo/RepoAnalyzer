module counter(
    input wire clk,
    input wire rst,
    output reg [3:0] count
);
    always @(posedge clk or posedge rst) begin
        if (rst)
            count <= 4'b0000;
        else
            count <= count + 1;
    end
endmodule

module test_module;
    function automatic [7:0] add;
        input [7:0] a, b;
        begin
            add = a + b;
        end
    endfunction

    task automatic print_value;
        input [7:0] value;
        begin
            $display("Value: %h", value);
        end
    endtask

    initial begin
        reg [7:0] x, y, result;
        x = 8'h5A;
        y = 8'h3C;
        result = add(x, y);
        print_value(result);
    end
endmodule 