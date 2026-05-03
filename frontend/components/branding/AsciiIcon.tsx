/**
 * Onchor seal — compact version (equivalent to CLI ASCII_ICON_SMALL).
 * Downsampled 1 line out of 3 + 1 char out of 3 from original.
 */
export const ASCII_ICON_SMALL = String.raw`                              
                  .              
                ....             
              .....::            
             .......::           
           ........:::           
          ...........            
         ........-:::::          
        ....:::::-----:::        
       .::::::::::-------::      
      ..    .:::::-----   :      
   .    ......::::-----    .     
   ...     ........::::      :   
   ......     ..::::::      :::  
   ........              :::::   
   ......::....:::::::::::::::   
       ............::::::::      
         ..........::::::        
            ......:::            
                .                
                                 `;

type Props = {
  className?: string;
};

export function AsciiIcon({ className = "" }: Props) {
  return (
    <pre
      aria-hidden
      className={[
        "font-mono leading-[1.05] whitespace-pre text-[--terminal-brand-dim]",
        className,
      ].join(" ")}
    >
      {ASCII_ICON_SMALL}
    </pre>
  );
}
