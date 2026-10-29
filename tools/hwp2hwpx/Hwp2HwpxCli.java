import kr.dogfoot.hwp2hwpx.Hwp2Hwpx;
import kr.dogfoot.hwplib.object.HWPFile;
import kr.dogfoot.hwplib.reader.HWPReader;
import kr.dogfoot.hwpxlib.object.HWPXFile;
import kr.dogfoot.hwpxlib.writer.HWPXWriter;

/** 사용법: java -jar hwp2hwpx-cli.jar <입력.hwp> <출력.hwpx> */
public class Hwp2HwpxCli {
    public static void main(String[] args) {
        if (args.length != 2) {
            System.err.println("usage: hwp2hwpx-cli <input.hwp> <output.hwpx>");
            System.exit(2);
        }
        try {
            HWPFile from = HWPReader.fromFile(args[0]);
            HWPXFile to = Hwp2Hwpx.toHWPX(from);
            HWPXWriter.toFilepath(to, args[1]);
        } catch (Exception e) {
            System.err.println("convert failed: " + e);
            e.printStackTrace();
            System.exit(1);
        }
    }
}
